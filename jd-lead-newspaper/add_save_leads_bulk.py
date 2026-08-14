#!/usr/bin/env python3
import sys
import argparse
import json
import subprocess
import uuid
import copy
import urllib.request
import urllib.error

WORKFLOW_ID = "zUbadDjZ9PfMR8av"
BACKUP_PATH = "/root/projects/lead-manger/jd-lead-newspaper/zUbadDjZ9PfMR8av_backup.json"

NESTED_CASE_SUBSTRING = "CASE WHEN $7 LIKE '%|%' THEN string_to_array($7, '|') ELSE CASE WHEN $7 LIKE '%|%' THEN string_to_array($7, '|') ELSE string_to_array($7, ',') END END"
FLATTENED_CASE_SUBSTRING = "CASE WHEN $7 LIKE '%|%' THEN string_to_array($7, '|') ELSE string_to_array($7, ',') END"

BULK_QUERY = """INSERT INTO leads (company_key, company_name, industry, size, city, roles_count, role_titles, posted_date, job_urls, contact_phone, contact_email, contact_source, company_website, score, tier, source_query, apply_count, role_group, industry_label, contact_name, contact_title, contact_linkedin, brand)
SELECT DISTINCT ON (r.company_key)
  r.company_key, r.company_name, r.industry, r.size, r.city,
  NULLIF(r.roles_count,'')::int,
  CASE WHEN r.role_titles LIKE '%|%' THEN string_to_array(r.role_titles,'|') ELSE string_to_array(r.role_titles,',') END,
  NULLIF(r.posted_date,'')::date,
  string_to_array(r.job_urls,','),
  r.contact_phone, r.contact_email, r.contact_source, r.company_website,
  NULLIF(r.score,'')::int, r.tier, r.source_query,
  NULLIF(r.apply_count,'')::int,
  r.role_group, r.industry_label, r.contact_name, r.contact_title, r.contact_linkedin, r.brand
FROM jsonb_to_recordset($1::jsonb) AS r(
  company_key text, company_name text, industry text, size text, city text,
  roles_count text, role_titles text, posted_date text, job_urls text,
  contact_phone text, contact_email text, contact_source text, company_website text,
  score text, tier text, source_query text, apply_count text, role_group text,
  industry_label text, contact_name text, contact_title text, contact_linkedin text, brand text)
ORDER BY r.company_key
ON CONFLICT (company_key) DO UPDATE SET
  roles_count = EXCLUDED.roles_count, role_titles = EXCLUDED.role_titles,
  posted_date = EXCLUDED.posted_date, job_urls = EXCLUDED.job_urls,
  score = EXCLUDED.score, tier = EXCLUDED.tier,
  source_query = COALESCE(leads.source_query, EXCLUDED.source_query),
  apply_count = EXCLUDED.apply_count, role_group = EXCLUDED.role_group,
  industry_label = EXCLUDED.industry_label,
  contact_name = COALESCE(leads.contact_name, EXCLUDED.contact_name),
  contact_title = COALESCE(leads.contact_title, EXCLUDED.contact_title),
  contact_linkedin = COALESCE(leads.contact_linkedin, EXCLUDED.contact_linkedin),
  updated_at = now()
RETURNING company_key, status"""

BULK_QUERY_REPLACEMENT = '={{ $fromAI("rows", "JSON array of lead objects, each carrying the same 23 fields as save_leads. Keep to 200 per call.", "string") }}'

BULK_TOOL_DESCRIPTION = "Upsert MANY leads in ONE call. Input: rows, a JSON array of objects each carrying the same 23 fields as save_leads. Same upsert semantics on company_key, never overwrites an existing status. Duplicate company_key values inside one batch are collapsed. ALWAYS set brand explicitly on every object. Prefer this over save_leads whenever saving more than one company."


def get_workflow_from_db(workflow_id: str):
    cmd = [
        "docker", "exec", "shared-postgres",
        "psql", "-U", "n8n_user", "-d", "n8n", "-Atc",
        f"SELECT json_build_object('nodes', nodes::jsonb, 'connections', connections::jsonb) FROM workflow_entity WHERE id='{workflow_id}';"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or not res.stdout.strip():
        print(f"Error fetching workflow from DB: {res.stderr}", file=sys.stderr)
        sys.exit(1)
    return json.loads(res.stdout.strip())


def reload_workflow_via_api(workflow_id: str) -> bool:
    cmd_key = ["docker", "exec", "shared-postgres", "psql", "-U", "n8n_user", "-d", "n8n", "-Atc", "SELECT \"apiKey\" FROM user_api_keys;"]
    try:
        res = subprocess.run(cmd_key, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr.strip() if e.stderr else str(e)
        print(f"[RELOAD WARNING] Failed to fetch API keys (exit code {e.returncode}): {err_msg}", file=sys.stderr)
        return False
    except OSError as e:
        print(f"[RELOAD WARNING] Failed to fetch API keys (OSError): {e}", file=sys.stderr)
        return False

    keys = [k.strip() for k in res.stdout.splitlines() if k.strip()]
    print(f"[RELOAD] Read {len(keys)} API key(s) from user_api_keys.")

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
                print("[TOGGLE] Workflow deactivated and reactivated via n8n REST API.")
                return True
        except urllib.error.HTTPError as e:
            print(f"[RELOAD WARNING] API key request failed with HTTPError: {e.code} {e.reason}", file=sys.stderr)
        except urllib.error.URLError as e:
            print(f"[RELOAD WARNING] API key request failed with URLError: {e.reason}", file=sys.stderr)
        except OSError as e:
            print(f"[RELOAD WARNING] API key request failed with OSError: {e}", file=sys.stderr)
    return False


def reload_workflow_via_db(workflow_id: str) -> bool:
    psql_script = f"""
UPDATE workflow_entity SET active = false WHERE id = '{workflow_id}';
UPDATE workflow_entity SET active = true WHERE id = '{workflow_id}';
"""
    cmd = ["docker", "exec", "-i", "shared-postgres", "psql", "-U", "n8n_user", "-d", "n8n"]
    res = subprocess.run(cmd, input=psql_script, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Error toggling workflow active state in DB: {res.stderr}", file=sys.stderr)
        return False
    print("[RELOAD DEGRADED] REST reload failed. Toggled workflow_entity.active in Postgres, which does NOT reload n8n in-memory. Reload the workflow in the n8n UI before using the new node.", file=sys.stderr)
    return True


def main():
    parser = argparse.ArgumentParser(description="Add save_leads_bulk node and flatten save_leads CASE in workflow zUbadDjZ9PfMR8av.")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without modifying database")
    args = parser.parse_args()

    data = get_workflow_from_db(WORKFLOW_ID)
    existing_nodes = data.get("nodes", [])
    existing_connections = data.get("connections", {})

    initial_node_count = len(existing_nodes)
    initial_conn_count = len(existing_connections)
    initial_cred_count = sum(1 for n in existing_nodes if "credentials" in n)

    if any(n.get("name") == "save_leads_bulk" for n in existing_nodes):
        print("Error: node 'save_leads_bulk' already exists in workflow.", file=sys.stderr)
        sys.exit(1)

    save_leads_node = next((n for n in existing_nodes if n.get("name") == "save_leads"), None)
    if not save_leads_node:
        print("Error: node 'save_leads' not found in workflow.", file=sys.stderr)
        sys.exit(1)

    if "credentials" not in save_leads_node:
        print("Error: 'save_leads' node does not have credentials.", file=sys.stderr)
        sys.exit(1)

    updated_nodes = copy.deepcopy(existing_nodes)
    target_save_leads = next(n for n in updated_nodes if n.get("name") == "save_leads")

    old_query = target_save_leads.get("parameters", {}).get("query", "")
    if NESTED_CASE_SUBSTRING not in old_query:
        print("Error: nested CASE substring not found in save_leads query.", file=sys.stderr)
        sys.exit(1)

    new_save_leads_query = old_query.replace(NESTED_CASE_SUBSTRING, FLATTENED_CASE_SUBSTRING, 1)
    if new_save_leads_query.replace(FLATTENED_CASE_SUBSTRING, NESTED_CASE_SUBSTRING, 1) != old_query:
        print("Error: query transformation did not strictly modify only the nested CASE substring.", file=sys.stderr)
        sys.exit(1)

    target_save_leads["parameters"]["query"] = new_save_leads_query

    node_id = str(uuid.uuid4())
    new_node = {
        "parameters": {
            "operation": "executeQuery",
            "query": BULK_QUERY,
            "options": {
                "queryReplacement": BULK_QUERY_REPLACEMENT
            },
            "descriptionType": "manual",
            "toolDescription": BULK_TOOL_DESCRIPTION
        },
        "name": "save_leads_bulk",
        "type": "n8n-nodes-base.postgresTool",
        "position": [336, 656],
        "credentials": save_leads_node["credentials"],
        "typeVersion": 2.6,
        "id": node_id
    }

    if json.dumps(new_node["credentials"], sort_keys=True) != json.dumps(save_leads_node["credentials"], sort_keys=True):
        print("Error: save_leads_bulk credentials block is not byte-identical to save_leads.", file=sys.stderr)
        sys.exit(1)

    updated_nodes.append(new_node)

    new_connection = {
        "save_leads_bulk": {
            "ai_tool": [
                [
                    {
                        "node": "MCP Server Trigger",
                        "type": "ai_tool",
                        "index": 0
                    }
                ]
            ]
        }
    }
    updated_connections = copy.deepcopy(existing_connections)
    updated_connections.update(new_connection)

    final_node_count = len(updated_nodes)
    final_conn_count = len(updated_connections)
    final_cred_count = sum(1 for n in updated_nodes if "credentials" in n)

    if final_cred_count != initial_cred_count + 1:
        print(f"Error: Unexpected credential count change: {initial_cred_count} -> {final_cred_count}", file=sys.stderr)
        sys.exit(1)

    # Verify all previous credential blocks were untouched
    for orig, updated in zip(existing_nodes, updated_nodes[:initial_node_count]):
        if orig.get("name") != "save_leads":
            if json.dumps(orig, sort_keys=True) != json.dumps(updated, sort_keys=True):
                print(f"Error: Untargeted node {orig.get('name')} was modified!", file=sys.stderr)
                sys.exit(1)
        else:
            if orig.get("credentials") != updated.get("credentials"):
                print("Error: save_leads credentials block was modified!", file=sys.stderr)
                sys.exit(1)

    print("=== WORKFLOW UPDATE ===")
    print(f"Workflow ID: {WORKFLOW_ID}")
    print(f"Nodes count: {initial_node_count} -> {final_node_count}")
    print(f"Connections count: {initial_conn_count} -> {final_conn_count}")
    print(f"Nodes carrying credentials: {initial_cred_count} -> {final_cred_count}")
    print("\n--- Change A: New node 'save_leads_bulk' ---")
    print(f"ID: {node_id}")
    print(f"Type: {new_node['type']} (v{new_node['typeVersion']})")
    print(f"Position: {new_node['position']}")
    print(f"Credentials key: {list(new_node['credentials'].keys())}")
    print(f"Query replacement: {new_node['parameters']['options']['queryReplacement']}")
    print(f"Tool description: {new_node['parameters']['toolDescription']}")
    print("\n--- Change B: save_leads Query diff ---")
    print("Old substring:", NESTED_CASE_SUBSTRING)
    print("New substring:", FLATTENED_CASE_SUBSTRING)

    if args.dry_run:
        print("\n[DRY RUN] No database changes written.")
        sys.exit(0)

    # Backup
    with open(BACKUP_PATH, "w") as f:
        json.dump(data, f)
    print(f"\n[BACKUP] Current workflow dumped to {BACKUP_PATH}")

    # Write updated nodes and connections to database
    nodes_json = json.dumps(updated_nodes)
    connections_json = json.dumps(updated_connections)

    psql_script = f"""
UPDATE workflow_entity SET nodes = :'nodes'::json, connections = :'conns'::json WHERE id = '{WORKFLOW_ID}';
UPDATE workflow_history SET nodes = :'nodes'::json, connections = :'conns'::json WHERE "workflowId" = '{WORKFLOW_ID}';
"""
    cmd = [
        "docker", "exec", "-i", "shared-postgres",
        "psql", "-U", "n8n_user", "-d", "n8n",
        "-v", f"nodes={nodes_json}",
        "-v", f"conns={connections_json}"
    ]
    res = subprocess.run(cmd, input=psql_script, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Error updating database: {res.stderr}", file=sys.stderr)
        sys.exit(1)

    print("[SUCCESS] Database updated successfully in workflow_entity and workflow_history.")

    if reload_workflow_via_api(WORKFLOW_ID):
        sys.exit(0)
    else:
        reload_workflow_via_db(WORKFLOW_ID)
        sys.exit(2)


if __name__ == "__main__":
    main()
