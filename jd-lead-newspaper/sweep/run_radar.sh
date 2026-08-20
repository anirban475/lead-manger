#!/usr/bin/env bash
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$(which python3)}"
LOG_DIR="/root/newspaper_sweep/logs"
LOCK_FILE="/root/newspaper_sweep/radar.lock"
TODAY="$(date +%Y-%m-%d)"
LOG_FILE="$LOG_DIR/radar-$TODAY.log"

mkdir -p "$LOG_DIR"

# Lock file guard: exit immediately if another run is in progress
exec 200>"$LOCK_FILE"
if ! flock -n 200; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Another radar sweep process is already running. Exiting." >&2
    exit 1
fi

# Clean up logs older than 30 days
find "$LOG_DIR" -name "radar-*.log" -type f -mtime +30 -delete

# Tee output to per-run log file
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=================================================="
echo "NEWSPAPER RADAR RUN START: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Log file: $LOG_FILE"
echo "=================================================="

# Stage 1: Sweep
echo ""
echo "=== STAGE 1: SWEEP ==="
"$PYTHON_BIN" "$SCRIPT_DIR/sweep.py" --days 1 --workers 4 --keyword-threshold 8
SWEEP_EXIT=$?
if [ $SWEEP_EXIT -ne 0 ]; then
    echo "" >&2
    echo "[ABORT] Stage 1 (sweep.py) failed with exit code $SWEEP_EXIT. Aborting pipeline before extract/dedup." >&2
    exit $SWEEP_EXIT
fi

# Stage 2: Extract
echo ""
echo "=== STAGE 2: EXTRACT ==="
"$PYTHON_BIN" "$SCRIPT_DIR/extract.py"
EXTRACT_EXIT=$?
if [ $EXTRACT_EXIT -ne 0 ]; then
    echo "" >&2
    echo "[ABORT] Stage 2 (extract.py) failed with exit code $EXTRACT_EXIT. Aborting pipeline before dedup." >&2
    exit $EXTRACT_EXIT
fi

# Stage 3: Dedup & Write
echo ""
echo "=== STAGE 3: DEDUP & WRITE ==="
LEADS_BEFORE=$(docker exec shared-postgres psql -U admin -d leads -Atc "SELECT count(*) FROM leads WHERE company_key LIKE 'np%';")
DEDUP_TMP=$(mktemp)
"$PYTHON_BIN" "$SCRIPT_DIR/dedup.py" --write | tee "$DEDUP_TMP"
DEDUP_EXIT="${PIPESTATUS[0]}"
if [ $DEDUP_EXIT -ne 0 ]; then
    rm -f "$DEDUP_TMP"
    echo "" >&2
    echo "[ABORT] Stage 3 (dedup.py) failed with exit code $DEDUP_EXIT." >&2
    exit $DEDUP_EXIT
fi

LEADS_AFTER=$(docker exec shared-postgres psql -U admin -d leads -Atc "SELECT count(*) FROM leads WHERE company_key LIKE 'np%';")
LEADS_LANDED=$(( LEADS_AFTER - LEADS_BEFORE ))

# Parse dedup metrics
NEW_LEADS=$(grep -i "New leads to insert:" "$DEDUP_TMP" | tail -n 1 | awk -F: '{print $2}' | tr -d ' ' || echo "0")
READV_LEADS=$(grep -i "Re-advertisements" "$DEDUP_TMP" | tail -n 1 | awk -F: '{print $2}' | awk '{print $1}' | tr -d ' ' || echo "0")
rm -f "$DEDUP_TMP"

[ -z "$NEW_LEADS" ] && NEW_LEADS=0
[ -z "$READV_LEADS" ] && READV_LEADS=0

if [ "$NEW_LEADS" -ne "$LEADS_LANDED" ]; then
    LEADS_SUMMARY="$LEADS_LANDED landed ($NEW_LEADS sent)"
else
    LEADS_SUMMARY="$LEADS_LANDED"
fi

# Stage 4: Apollo Enrichment (must run AFTER dedup so credits are only
# ever spent on leads that actually survived into the database)
echo ""
echo "=== STAGE 4: APOLLO ENRICHMENT ==="
ENRICH_TMP=$(mktemp)
set +e
"$PYTHON_BIN" "$SCRIPT_DIR/enrich.py" --write | tee "$ENRICH_TMP"
ENRICH_EXIT="${PIPESTATUS[0]}"
set -e
if [ $ENRICH_EXIT -ne 0 ]; then
    rm -f "$ENRICH_TMP"
    echo "" >&2
    echo "[ABORT] Stage 4 (enrich.py) failed with exit code $ENRICH_EXIT." >&2
    exit $ENRICH_EXIT
fi

CREDITS_SPENT=$(grep -i "Total actual credits spent:" "$ENRICH_TMP" | tail -n 1 | awk -F: '{print $2}' | awk '{print $1}' | tr -d ' ' || echo "0")
PH_DIRECT=$(grep -i "Direct person phones resolved" "$ENRICH_TMP" | tail -n 1 | awk -F: '{print $2}' | tr -d ' ' || echo "0")
PH_ORG=$(grep -i "Organization phones resolved" "$ENRICH_TMP" | tail -n 1 | awk -F: '{print $2}' | tr -d ' ' || echo "0")
rm -f "$ENRICH_TMP"

[ -z "$CREDITS_SPENT" ] && CREDITS_SPENT=0
[ -z "$PH_DIRECT" ] && PH_DIRECT=0
[ -z "$PH_ORG" ] && PH_ORG=0
PHONES_RESOLVED=$(( PH_DIRECT + PH_ORG ))

# Extract page scan metrics and qualified leads count
METRICS_JSON=$("$PYTHON_BIN" -c "
import sqlite3, json, sys

db_path = '/root/newspaper_sweep/sweep.db'
scanned, failed = 0, 0
try:
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute('SELECT max(edition_date) FROM page_scan')
        row = cur.fetchone()
        max_date = row[0] if row else None
        if max_date:
            cur.execute('SELECT count(*), sum(case when status != \'ok\' then 1 else 0 end) FROM page_scan WHERE edition_date = ?', (max_date,))
            r = cur.fetchone()
            if r:
                scanned = r[0] or 0
                failed = r[1] or 0
except Exception:
    pass

report_path = '/root/newspaper_sweep/extract_report.json'
qualified = 0
try:
    with open(report_path) as f:
        rep = json.load(f)
    qualified = rep.get('survivors_summary', {}).get('total_survivors', 0)
except Exception:
    pass

print(json.dumps({'scanned': scanned, 'failed': failed, 'qualified': qualified}))
")

PAGES_SCANNED=$(echo "$METRICS_JSON" | "$PYTHON_BIN" -c "import sys, json; print(json.load(sys.stdin).get('scanned', 0))")
PAGES_FAILED=$(echo "$METRICS_JSON" | "$PYTHON_BIN" -c "import sys, json; print(json.load(sys.stdin).get('failed', 0))")
QUALIFIED_LEADS=$(echo "$METRICS_JSON" | "$PYTHON_BIN" -c "import sys, json; print(json.load(sys.stdin).get('qualified', 0))")

echo ""
echo "=================================================="
echo "RADAR RUN COMPLETED: $(date '+%Y-%m-%d %H:%M:%S')"
echo "SUMMARY: pages scanned: $PAGES_SCANNED, pages failed: $PAGES_FAILED, qualified leads: $QUALIFIED_LEADS, new leads written: $LEADS_SUMMARY, re-advertisements: $READV_LEADS, credits spent: $CREDITS_SPENT, phones resolved: $PHONES_RESOLVED"
echo "=================================================="
