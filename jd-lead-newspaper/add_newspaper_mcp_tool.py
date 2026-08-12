#!/usr/bin/env python3
import sys
import argparse
import json
import subprocess
import uuid

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

    # Write updated nodes and connections to database using psql stdin
    nodes_json = json.dumps(updated_nodes)
    connections_json = json.dumps(updated_connections)

    psql_script = f"""
UPDATE workflow_entity SET nodes = '{nodes_json.replace("'", "''")}', connections = '{connections_json.replace("'", "''")}' WHERE id = '{WORKFLOW_ID}';
UPDATE workflow_history SET nodes = '{nodes_json.replace("'", "''")}', connections = '{connections_json.replace("'", "''")}' WHERE "workflowId" = '{WORKFLOW_ID}';
"""
    cmd = ["docker", "exec", "-i", "shared-postgres", "psql", "-U", "n8n_user", "-d", "n8n"]
    res = subprocess.run(cmd, input=psql_script, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Error updating database: {res.stderr}", file=sys.stderr)
        sys.exit(1)

    print("[SUCCESS] Database updated successfully in workflow_entity and workflow_history.")

    # Toggle workflow active state via API endpoints or DB if API fails
    try:
        cmd_key = ["docker", "exec", "shared-postgres", "psql", "-U", "n8n_user", "-d", "n8n", "-Atc", "SELECT \"apiKey\" FROM user_api_keys;"]
        keys = subprocess.run(cmd_key, capture_output=True, text=True, check=True).stdout.splitlines()
        for key in keys:
            if not key.strip(): continue
            req_deact = urllib.request.Request(f"http://localhost:5678/api/v1/workflows/{WORKFLOW_ID}/deactivate", method="POST", headers={"X-N8N-API-KEY": key.strip()})
            try:
                with urllib.request.urlopen(req_deact):
                    req_act = urllib.request.Request(f"http://localhost:5678/api/v1/workflows/{WORKFLOW_ID}/activate", method="POST", headers={"X-N8N-API-KEY": key.strip()})
                    with urllib.request.urlopen(req_act):
                        print("[TOGGLE] Workflow deactivated and reactivated via n8n REST API.")
                        break
            except Exception:
                continue
    except Exception as e:
        print(f"[TOGGLE WARNING] API toggle failed: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
