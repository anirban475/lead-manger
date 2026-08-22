#!/usr/bin/env python3
"""
tools/backfill_leads_routing.py

Backfills routing columns on public.leads:
  - offer: text
  - trigger_type: text
  - buyer_level: text ('owner', 'head', 'individual')
  - country: char(2)

Dry-run is the default. Pass --apply to write changes to PostgreSQL.
"""

import argparse
import json
import re
import subprocess
import sys
from collections import Counter

# Country tail mapping for Amatec source_queries
COUNTRY_MAP = {
    'US': 'US',
    'UK': 'GB',
    'AU': 'AU',
    'FR': 'FR',
    'IE': 'IE',
    'Canada': 'CA',
}

# Seniority keyword lists for buyer_level derivation
OWNER_KEYWORDS = ['owner', 'founder', 'ceo', 'president', 'partner', 'proprietor', 'director']
HEAD_KEYWORDS = ['head', 'vp', 'vice president', 'manager', 'lead', 'chief']


def is_usable_email(email):
    return email is not None and email.strip() != '' and email.strip() != '-'


def resolve_buyer_level(title):
    if not title or not title.strip():
        return None
    t = title.lower().replace('&amp;', '&')
    
    # Priority check: 'vice president' / 'vp' goes to 'head' before 'president' matches 'owner'
    if re.search(r'\b(vp|vice president)\b', t):
        return 'head'
    
    for kw in OWNER_KEYWORDS:
        if re.search(r'\b' + re.escape(kw) + r'\b', t):
            return 'owner'
            
    for kw in HEAD_KEYWORDS:
        if re.search(r'\b' + re.escape(kw) + r'\b', t):
            return 'head'
            
    return 'individual'


def parse_lead(lead):
    brand = lead.get('brand')
    sq_raw = lead.get('source_query')
    sq = (sq_raw or '').strip()
    title_raw = lead.get('contact_title')
    title = (title_raw or '').strip()
    email = lead.get('contact_email') or ''
    usable_email = is_usable_email(email)

    # 1. Offer
    # Derived from brand only because exactly one offer per brand is live today;
    # the column exists so a second offer has somewhere to go. Not permanent brand->offer logic.
    if brand == 'amatec':
        offer = 'automation'
    elif brand == 'jobdrive':
        offer = 'resume_screening'
    else:
        offer = None

    # 2. Buyer Level
    buyer_level = resolve_buyer_level(title)

    # 3. Trigger Type & Country
    trigger_type = None
    country = None
    sq_unparseable_reason = None

    if not sq:
        sq_unparseable_reason = 'Empty or missing source_query'
    elif brand == 'amatec':
        trigger_type = 'ops_role_posted'
        if '|' in sq:
            parts = [p.strip() for p in sq.split('|', 1)]
            geo_part = parts[1]

            # Derive country
            if geo_part == 'multi-geo':
                country = None  # multi-geo means no specific country
            elif geo_part == 'CA':
                country = None
                sq_unparseable_reason = 'Ambiguous country code CA (Canada vs California) -> left null'
            elif geo_part in COUNTRY_MAP:
                country = COUNTRY_MAP[geo_part]
            else:
                sq_unparseable_reason = f'Unrecognized country tail: {geo_part}'
        else:
            sq_unparseable_reason = f'Unrecognized source_query format: {sq}'
    elif brand == 'jobdrive':
        country = 'IN'  # Jobdrive leads are India-focused
        if sq.startswith('newspaper |'):
            trigger_type = 'newspaper'
        elif sq.startswith('linkedin post'):
            trigger_type = 'linkedin_post'
        elif '|' in sq or 'Naukri' in sq or 'Indeed' in sq:
            trigger_type = 'job_board'
        else:
            trigger_type = 'job_board'

    return {
        'company_key': lead['company_key'],
        'brand': brand,
        'has_usable_email': usable_email,
        'offer': offer,
        'buyer_level': buyer_level,
        'trigger_type': trigger_type,
        'country': country,
        'sq_raw': sq_raw,
        'title_raw': title_raw,
        'sq_unparseable_reason': sq_unparseable_reason
    }


def fetch_leads():
    cmd = [
        'docker', 'exec', 'shared-postgres', 'psql',
        '-U', 'admin', '-d', 'leads', '-t', '-A',
        '-c', 'SELECT json_agg(t) FROM (SELECT company_key, brand, source_query, contact_title, contact_email FROM leads) t;'
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    out = res.stdout.strip()
    if not out:
        return []
    return json.loads(out)


def apply_backfill(parsed_leads):
    # Prepare SQL statements in a single transaction
    statements = ['BEGIN;']
    for p in parsed_leads:
        ck = p['company_key'].replace("'", "''")
        offer_val = f"'{p['offer']}'" if p['offer'] is not None else "NULL"
        trigger_val = f"'{p['trigger_type']}'" if p['trigger_type'] is not None else "NULL"
        buyer_val = f"'{p['buyer_level']}'" if p['buyer_level'] is not None else "NULL"
        country_val = f"'{p['country']}'" if p['country'] is not None else "NULL"
        
        stmt = (
            f"UPDATE leads SET "
            f"offer = {offer_val}, "
            f"trigger_type = {trigger_val}, "
            f"buyer_level = {buyer_val}, "
            f"country = {country_val} "
            f"WHERE company_key = '{ck}';"
        )
        statements.append(stmt)
    statements.append('COMMIT;')
    
    sql_script = '\n'.join(statements)
    proc = subprocess.run(
        ['docker', 'exec', '-i', 'shared-postgres', 'psql', '-U', 'admin', '-d', 'leads', '-v', 'ON_ERROR_STOP=1'],
        input=sql_script, text=True, capture_output=True
    )
    if proc.returncode != 0:
        sys.stderr.write(f"Error applying backfill:\n{proc.stderr}\n")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Backfill routing columns on leads table")
    parser.add_argument('--apply', action='store_true', help="Apply changes to the database (default: dry run)")
    args = parser.parse_args()

    mode_label = "APPLY MODE" if args.apply else "DRY RUN (no database changes)"
    print(f"=== LEADS ROUTING BACKFILL: {mode_label} ===\n")

    leads = fetch_leads()
    print(f"Total leads loaded: {len(leads)}\n")

    parsed = [parse_lead(l) for l in leads]

    # --- Summary Table ---
    print("-------------------------------- SUMMARY TABLE --------------------------------")
    print(f"{'Brand':<10} | {'Column':<28} | {'Resolved':<10} | {'Null':<10} | {'Total':<10}")
    print("-" * 79)

    for b in ['amatec', 'jobdrive']:
        b_leads = [p for p in parsed if p['brand'] == b]
        b_email_leads = [p for p in b_leads if p['has_usable_email']]
        total_b = len(b_leads)
        total_email_b = len(b_email_leads)

        for col in ['offer', 'trigger_type', 'country']:
            res_cnt = sum(1 for p in b_leads if p[col] is not None)
            null_cnt = sum(1 for p in b_leads if p[col] is None)
            print(f"{b:<10} | {col:<28} | {res_cnt:<10} | {null_cnt:<10} | {total_b:<10}")

        bl_email_res = sum(1 for p in b_email_leads if p['buyer_level'] is not None)
        bl_email_null = sum(1 for p in b_email_leads if p['buyer_level'] is None)
        print(f"{b:<10} | {'buyer_level (email-bearing)':<28} | {bl_email_res:<10} | {bl_email_null:<10} | {total_email_b:<10}")

        bl_all_res = sum(1 for p in b_leads if p['buyer_level'] is not None)
        bl_all_null = sum(1 for p in b_leads if p['buyer_level'] is None)
        print(f"{b:<10} | {'buyer_level (all rows)':<28} | {bl_all_res:<10} | {bl_all_null:<10} | {total_b:<10}")
        print("-" * 79)

    # --- Unparseable Report ---
    print("\n============================= UNPARSEABLE REPORT =============================")
    print("1. Unparseable / Ambiguous source_query values:")
    unparseable_sq = Counter()
    for p in parsed:
        if p['sq_unparseable_reason']:
            unparseable_sq[(p['brand'], p['sq_raw'], p['sq_unparseable_reason'])] += 1

    if unparseable_sq:
        for (b, sq, reason), count in unparseable_sq.most_common():
            sq_display = repr(sq) if sq is not None else "None"
            print(f"  - [{b}] {count} row(s): {sq_display} -> {reason}")
    else:
        print("  None.")

    print("\n2. Unparseable / Empty contact_title values (email-bearing leads):")
    unparseable_title_email = Counter()
    for p in parsed:
        if p['has_usable_email'] and p['buyer_level'] is None:
            unparseable_title_email[(p['brand'], p['title_raw'])] += 1

    if unparseable_title_email:
        for (b, title), count in unparseable_title_email.most_common():
            t_display = repr(title) if title is not None else "None"
            print(f"  - [{b}] {count} row(s): {t_display} -> Empty or null contact_title on email-bearing row")
    else:
        print("  None (all email-bearing leads resolved to a valid buyer_level).")

    print("\n3. Empty contact_title values (across all rows):")
    unparseable_title_all = Counter()
    for p in parsed:
        if p['buyer_level'] is None:
            unparseable_title_all[(p['brand'], p['title_raw'])] += 1

    for (b, title), count in unparseable_title_all.most_common():
        t_display = repr(title) if title is not None else "None"
        print(f"  - [{b}] {count} row(s): {t_display} -> Missing/empty title (left buyer_level null)")

    print("==============================================================================\n")

    if args.apply:
        print("Applying backfill updates to database...")
        apply_backfill(parsed)
        print("Backfill applied successfully in a single transaction.")
    else:
        print("Dry run complete. No changes were made to the database.")

    sys.exit(0)


if __name__ == '__main__':
    main()
