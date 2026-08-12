#!/usr/bin/env python3
import sys
import argparse
import json
import subprocess
import uuid
import urllib.request
import urllib.error

WORKFLOW_ID = "zUbadDjZ9PfMR8av"
BACKUP_PATH = "/root/projects/lead-manger/jd-lead-newspaper/zUbadDjZ9PfMR8av_backup.json"

def get_workflow_from_db(workflow_id):
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
    res = subprocess.run(cmd_key, capture_output=True, text=True, check=True)
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
    print("[RELOAD DEGRADED] REST reload failed. Toggled workflow_entity.active in Postgres, which does NOT reload n8n in-memory. Reload the workflow in the n8n UI before using the new node.", file=sys.stderr)
    psql_script = f"""
UPDATE workflow_entity SET active = false WHERE id = '{workflow_id}';
UPDATE workflow_entity SET active = true WHERE id = '{workflow_id}';
"""
    cmd = ["docker", "exec", "-i", "shared-postgres", "psql", "-U", "n8n_user", "-d", "n8n"]
    res = subprocess.run(cmd, input=psql_script, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Error toggling workflow active state in DB: {res.stderr}", file=sys.stderr)
        return False
    return True

def main():
    parser = argparse.ArgumentParser(description="Add fetch_newspaper_ads node to n8n workflow zUbadDjZ9PfMR8av.")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without modifying database")
    args = parser.parse_args()

    data = get_workflow_from_db(WORKFLOW_ID)
    existing_nodes = data.get("nodes", [])
    existing_connections = data.get("connections", {})

    initial_node_count = len(existing_nodes)
    initial_conn_count = len(existing_connections)
    initial_cred_count = sum(1 for n in existing_nodes if "credentials" in n)

    if any(n.get("name") == "fetch_newspaper_ads" for n in existing_nodes):
        print("Error: node 'fetch_newspaper_ads' already exists in workflow.", file=sys.stderr)
        sys.exit(1)

    node_id = str(uuid.uuid4())
    new_node = {
        "parameters": {
            "toolDescription": "Fetch one day's recruitment ads for a single publication from Ads2Publish, parsed server-side from raw HTML so no ads are lost. Input: slug (e.g. times-of-india, dainik-jagran, eenadu). Returns classifiedCount, displayCount, highestAdIndex, missingIndices (should always be empty; a non-empty value means the source itself skipped an ad number) and ads[] with adType, adIndex, body, category (full path), email, phone. Use this instead of WebFetch, which silently drops ads.",
            "method": "POST",
            "url": "https://n8n.amatec.in/webhook/newspaper-ads",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify({ slug: $fromAI(\"slug\", \"Ads2Publish publication slug, e.g. times-of-india or dainik-jagran\", \"string\") }) }}",
            "options": {
                "timeout": 60000
            }
        },
        "name": "fetch_newspaper_ads",
        "type": "n8n-nodes-base.httpRequestTool",
        "position": [1360, 528],
        "typeVersion": 4.4,
        "id": node_id
    }

    new_connection = {
        "fetch_newspaper_ads": {
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

    updated_nodes = list(existing_nodes) + [new_node]
    updated_connections = dict(existing_connections)
    updated_connections.update(new_connection)

    final_node_count = len(updated_nodes)
    final_conn_count = len(updated_connections)
    final_cred_count = sum(1 for n in updated_nodes if "credentials" in n)

    if final_cred_count != initial_cred_count:
        print(f"Error: Credential count changed from {initial_cred_count} to {final_cred_count}!", file=sys.stderr)
        sys.exit(1)

    print("=== WORKFLOW UPDATE ===")
    print(f"Workflow ID: {WORKFLOW_ID}")
    print(f"Nodes count: {initial_node_count} -> {final_node_count}")
    print(f"Connections count: {initial_conn_count} -> {final_conn_count}")
    print(f"Nodes carrying credentials: {initial_cred_count} -> {final_cred_count}")

    if args.dry_run:
        print("\n[DRY RUN] No database changes written.")
        sys.exit(0)

    # Perform backup before real write
    with open(BACKUP_PATH, "w") as f:
        json.dump(data, f)
    print(f"\n[BACKUP] Current workflow dumped to {BACKUP_PATH}")

    # Write updated nodes and connections to database using psql stdin and variables
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
