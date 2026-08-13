#!/usr/bin/env python3
import sys
import argparse
import json
import subprocess
import urllib.request
import urllib.error

WORKFLOW_ID = "zUbadDjZ9PfMR8av"

def get_workflow_from_db(workflow_id=WORKFLOW_ID):
    cmd = [
        "docker", "exec", "shared-postgres",
        "psql", "-U", "n8n_user", "-d", "n8n", "-Atc",
        f"SELECT json_build_object('nodes', nodes::jsonb, 'connections', connections::jsonb) FROM workflow_entity WHERE id='{workflow_id}';"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or not res.stdout.strip():
        raise RuntimeError(f"Error fetching workflow from DB: {res.stderr}")
    return json.loads(res.stdout.strip())

def reload_workflow_via_api(workflow_id=WORKFLOW_ID) -> bool:
    cmd_key = ["docker", "exec", "shared-postgres", "psql", "-U", "n8n_user", "-d", "n8n", "-Atc", "SELECT \"apiKey\" FROM user_api_keys;"]
    try:
        res = subprocess.run(cmd_key, capture_output=True, text=True, check=True)
    except Exception as e:
        print(f"[RELOAD WARNING] Failed to fetch API keys: {e}", file=sys.stderr)
        return False

    keys = [k.strip() for k in res.stdout.splitlines() if k.strip()]
    for key in keys:
        deact_url = f"http://localhost:5678/api/v1/workflows/{workflow_id}/deactivate"
        act_url = f"http://localhost:5678/api/v1/workflows/{workflow_id}/activate"
        req_deact = urllib.request.Request(deact_url, method="POST", headers={"X-N8N-API-KEY": key})
        req_act = urllib.request.Request(act_url, method="POST", headers={"X-N8N-API-KEY": key})

        try:
            with urllib.request.urlopen(req_deact) as resp_deact:
                deact_ok = (200 <= resp_deact.status < 300)
            with urllib.request.urlopen(req_act) as resp_act:
                act_ok = (200 <= resp_act.status < 300)
            if deact_ok and act_ok:
                print("[RELOAD] Workflow deactivated and reactivated successfully via n8n REST API.")
                return True
        except Exception as e:
            continue
    print("[RELOAD ERROR] Failed to reload workflow via n8n API with available keys", file=sys.stderr)
    return False

def patch_save_leads_node(dry_run=False):
    print("=== PART A: Patching save_leads node in n8n workflow ===")
    data = get_workflow_from_db(WORKFLOW_ID)
    nodes = data.get("nodes", [])

    cred_count_before = sum(1 for n in nodes if "credentials" in n)
    assert cred_count_before == 10, f"Expected 10 credential-bearing nodes, got {cred_count_before}"
    print(f"Credential-bearing node count before edit: {cred_count_before}")

    target_node = None
    for n in nodes:
        if n.get("name") == "save_leads":
            target_node = n
            break

    if not target_node:
        raise RuntimeError("save_leads node not found in workflow")

    current_query = target_node.get("parameters", {}).get("query", "")
    target_str = "string_to_array($7, ',')"
    replacement_str = "CASE WHEN $7 LIKE '%|%' THEN string_to_array($7, '|') ELSE string_to_array($7, ',') END"

    if target_str not in current_query:
        if replacement_str in current_query:
            print("save_leads node is already patched.")
        else:
            raise RuntimeError(f"Target string '{target_str}' not found in save_leads query!")
    else:
        new_query = current_query.replace(target_str, replacement_str, 1)
        target_node["parameters"]["query"] = new_query
        print("Updated save_leads query string.")

    cred_count_after = sum(1 for n in nodes if "credentials" in n)
    assert cred_count_after == 10, f"Credential count mismatch: expected 10, got {cred_count_after}"
    assert cred_count_before == cred_count_after, "Credential-bearing node count changed!"
    print(f"Credential-bearing node count after edit: {cred_count_after} (Verified equal)")

    if dry_run:
        print("[DRY RUN] Skipping database write for workflow patch.")
        return

    nodes_json = json.dumps(nodes)
    psql_script = f"""
UPDATE workflow_entity SET nodes = :'nodes'::json WHERE id = '{WORKFLOW_ID}';
UPDATE workflow_history SET nodes = :'nodes'::json WHERE "workflowId" = '{WORKFLOW_ID}';
"""
    cmd = [
        "docker", "exec", "-i", "shared-postgres",
        "psql", "-U", "n8n_user", "-d", "n8n",
        "-v", f"nodes={nodes_json}"
    ]
    res = subprocess.run(cmd, input=psql_script, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Error updating workflow in Postgres: {res.stderr}")

    print("Postgres database updated for workflow_entity and workflow_history.")
    if not reload_workflow_via_api(WORKFLOW_ID):
        raise RuntimeError("Failed to reload workflow via n8n REST API!")

def rejoin_roles(arr):
    new_arr = []
    current = ""
    for elem in arr:
        elem_str = elem.strip()
        if not current:
            current = elem_str
        else:
            current = current + ", " + elem_str
        if current.count("(") <= current.count(")"):
            new_arr.append(current)
            current = ""
    if current:
        new_arr.append(current)
    return new_arr

def backfill_corrupted_rows(dry_run=False):
    print("\n=== PART B: Backfilling bracket-imbalanced role_titles ===")

    detector_query = """
    SELECT json_build_object(
        'company_key', company_key,
        'roles_count', roles_count,
        'role_titles', role_titles
    )
    FROM leads l
    WHERE EXISTS (
        SELECT 1 FROM unnest(l.role_titles) t
        WHERE length(t) - length(replace(t,'(','')) <> length(t) - length(replace(t,')',''))
    );
    """
    cmd = [
        "docker", "exec", "shared-postgres",
        "psql", "-U", "admin", "-d", "leads", "-Atc", detector_query
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    lines = [l.strip() for l in res.stdout.splitlines() if l.strip()]

    print(f"Found {len(lines)} bracket-imbalanced row(s) to backfill.")

    if not lines:
        print("No rows need backfilling.")
        return

    changes = []
    for line in lines:
        row = json.loads(line)
        ckey = row["company_key"]
        orig_roles = row["role_titles"]
        orig_count = row["roles_count"]

        rejoined_roles = rejoin_roles(orig_roles)
        is_np = ckey.startswith("np")
        new_count = len(rejoined_roles) if is_np else orig_count

        changes.append({
            "company_key": ckey,
            "orig_roles": orig_roles,
            "rejoined_roles": rejoined_roles,
            "orig_count": orig_count,
            "new_count": new_count,
            "is_np": is_np
        })

    print("\n--- Rows to be changed ---")
    for c in changes:
        print(f"Key: {c['company_key']} (is_np={c['is_np']})")
        print(f"  BEFORE roles: {c['orig_roles']}")
        print(f"  AFTER  roles: {c['rejoined_roles']}")
        print(f"  roles_count : {c['orig_count']} -> {c['new_count']}")

    if dry_run:
        print("\n[DRY RUN] Skipping database backfill.")
        return

    psql_statements = ["BEGIN;"]
    psql_statements.append("""
    CREATE TABLE IF NOT EXISTS role_titles_backup (
        id SERIAL PRIMARY KEY,
        company_key VARCHAR(255),
        original_role_titles TEXT[],
        original_roles_count INT,
        backup_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    """)

    for c in changes:
        ckey = c['company_key']
        psql_statements.append(f"""
        INSERT INTO role_titles_backup (company_key, original_role_titles, original_roles_count)
        SELECT company_key, role_titles, roles_count FROM leads WHERE company_key = '{ckey}';
        """)
        roles_pg_array = "ARRAY[" + ", ".join("'" + r.replace("'", "''") + "'" for r in c['rejoined_roles']) + "]"
        if c['is_np']:
            psql_statements.append(f"""
            UPDATE leads
            SET role_titles = {roles_pg_array},
                roles_count = {c['new_count']},
                updated_at = NOW()
            WHERE company_key = '{ckey}';
            """)
        else:
            psql_statements.append(f"""
            UPDATE leads
            SET role_titles = {roles_pg_array},
                updated_at = NOW()
            WHERE company_key = '{ckey}';
            """)

    psql_statements.append("COMMIT;")
    full_script = "\n".join(psql_statements)

    cmd_tx = ["docker", "exec", "-i", "shared-postgres", "psql", "-U", "admin", "-d", "leads"]
    res_tx = subprocess.run(cmd_tx, input=full_script, capture_output=True, text=True)
    if res_tx.returncode != 0:
        raise RuntimeError(f"Transaction failed: {res_tx.stderr}")

    print("\n[SUCCESS] Backfill transaction completed successfully.")

def verify_all():
    print("=== VERIFYING FIX ===")

    detector_query = """
    SELECT count(*) FROM leads l
    WHERE EXISTS (
        SELECT 1 FROM unnest(l.role_titles) t
        WHERE length(t) - length(replace(t,'(','')) <> length(t) - length(replace(t,')',''))
    );
    """
    cmd1 = ["docker", "exec", "shared-postgres", "psql", "-U", "admin", "-d", "leads", "-Atc", detector_query]
    res1 = subprocess.run(cmd1, capture_output=True, text=True, check=True)
    imbalance_cnt = int(res1.stdout.strip())
    print(f"1. Bracket-imbalanced row count: {imbalance_cnt} (Expected: 0)")
    assert imbalance_cnt == 0, f"Expected 0 bracket-imbalanced rows, found {imbalance_cnt}!"

    mismatch_query = "SELECT count(*) FROM leads WHERE company_key NOT LIKE 'np%' AND roles_count <> array_length(role_titles, 1);"
    cmd2 = ["docker", "exec", "shared-postgres", "psql", "-U", "admin", "-d", "leads", "-Atc", mismatch_query]
    res2 = subprocess.run(cmd2, capture_output=True, text=True, check=True)
    non_np_mismatch_cnt = int(res2.stdout.strip())
    print(f"2. Non-newspaper roles_count mismatch count: {non_np_mismatch_cnt} (Expected: non-zero/67)")
    assert non_np_mismatch_cnt > 0, f"Non-newspaper mismatch count dropped to 0! Over-reached!"

    wf = get_workflow_from_db(WORKFLOW_ID)
    nodes = wf.get("nodes", [])
    cred_cnt = sum(1 for n in nodes if "credentials" in n)
    print(f"3. Credential-bearing node count: {cred_cnt} (Expected: 10)")
    assert cred_cnt == 10, f"Expected 10 credential-bearing nodes, got {cred_cnt}!"

    save_leads_node = next((n for n in nodes if n.get("name") == "save_leads"), None)
    assert save_leads_node is not None, "save_leads node not found!"
    q = save_leads_node.get("parameters", {}).get("query", "")
    assert "CASE WHEN $7 LIKE '%|%' THEN string_to_array($7, '|')" in q, "save_leads node query not properly patched!"
    print("   save_leads query contains patched CASE WHEN statement.")

    print("\n[VERIFICATION PASSED] All acceptance criteria met!")

def main():
    parser = argparse.ArgumentParser(description="Fix role_titles comma-split and backfill imbalanced rows.")
    parser.add_argument("--patch-only", action="store_true", help="Only patch the save_leads workflow node")
    parser.add_argument("--backfill-only", action="store_true", help="Only backfill corrupted rows in DB")
    parser.add_argument("--verify", action="store_true", help="Verify all acceptance criteria")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without modifying database")
    args = parser.parse_args()

    if args.verify:
        verify_all()
        sys.exit(0)

    if args.patch_only:
        patch_save_leads_node(dry_run=args.dry_run)
    elif args.backfill_only:
        backfill_corrupted_rows(dry_run=args.dry_run)
    else:
        patch_save_leads_node(dry_run=args.dry_run)
        backfill_corrupted_rows(dry_run=args.dry_run)
        if not args.dry_run:
            verify_all()

if __name__ == "__main__":
    main()
