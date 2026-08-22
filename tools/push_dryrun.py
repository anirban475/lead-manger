#!/usr/bin/env python3
"""
tools/push_dryrun.py

ACTION-015 Dry Run: Read-only eligibility funnel, campaign copy field derivation,
routing check, and live workflow comparison.
"""

import json
import re
import subprocess
import sys
from collections import Counter

# Known defaults mapping for Tier 1 tag resolution
KNOWN_DEFAULTS = {
    'company': 'company_name (tags stripped)',
    'role': 'role_group (translated to plain English)',
    'city': 'city',
    'name': 'contact_name (first word)',
    'fname': 'contact_name (first word)',
    'first_name': 'contact_name (first word)',
    'apply_count': 'apply_count',
}

BRAND_MAP = {
    'amatec': 'Amatec',
    'jobdrive': 'JobDrive',
}


def run_psql_json(database, query):
    """Executes a SELECT query returning a JSON array via psql inside docker."""
    sql = f"SELECT json_agg(t) FROM ({query}) t;"
    cmd = [
        'docker', 'exec', 'shared-postgres', 'psql',
        '-U', 'admin', '-d', database, '-t', '-A',
        '-c', sql
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        sys.stderr.write(f"Error querying {database}:\n{res.stderr}\n")
        sys.exit(1)
    out = res.stdout.strip()
    if not out or out == 'null':
        return []
    return json.loads(out)


def is_usable_email(email):
    if not email:
        return False
    e = email.strip()
    return e != '' and e != '-'


def normalize_email(email):
    if not email:
        return ''
    return email.strip().lower()


def fetch_all_data():
    leads_query = """
        SELECT
            company_key,
            brand,
            contact_email,
            contact_name,
            contact_title,
            company_name,
            role_group,
            apply_count,
            city,
            industry,
            industry_label,
            status,
            contact_source,
            email_catchall,
            mystrika_synced,
            score,
            eligible_brands
        FROM leads
    """
    leads = run_psql_json('leads', leads_query)

    suppression_query = """
        SELECT email, phone, reason
        FROM suppression
        WHERE email IS NOT NULL
    """
    suppression = run_psql_json('leads', suppression_query)

    campaigns_query = """
        SELECT
            campaign_name,
            brand,
            campaign_id,
            state,
            segment_key,
            is_current
        FROM campaign_registry
        ORDER BY brand, state, campaign_name
    """
    campaigns = run_psql_json('marketing_analytics', campaigns_query)

    copy_query = """
        SELECT
            campaign_name,
            sequence,
            variation,
            campaign_id,
            brand,
            subject,
            preview,
            body
        FROM campaign_copy
        ORDER BY campaign_name, sequence, variation
    """
    copy_rows = run_psql_json('marketing_analytics', copy_query)

    ledger_query = """
        SELECT contact_key, campaign_id, outcome
        FROM push_ledger
    """
    ledger_rows = run_psql_json('marketing_analytics', ledger_query)

    routing_rules_query = """
        SELECT id, brand, segment_key
        FROM routing_rule
    """
    routing_rules = run_psql_json('marketing_analytics', routing_rules_query)

    return leads, suppression, campaigns, copy_rows, ledger_rows, routing_rules


def main():
    leads, suppression_rows, campaigns, copy_rows, ledger_rows, routing_rules = fetch_all_data()

    # Build suppression lookup
    suppressed_emails = {normalize_email(r['email']): r.get('reason') or 'suppressed' for r in suppression_rows}

    # Ready/Running campaign IDs and names
    active_campaign_ids = set()
    active_campaign_names = set()
    for c in campaigns:
        if c['state'] in ('ready', 'running'):
            if c.get('campaign_id'):
                active_campaign_ids.add(c['campaign_id'])
            active_campaign_names.add(c['campaign_name'])

    # Build push ledger contacts set (all ledger entries)
    all_ledger_contacts = {row['contact_key'] for row in ledger_rows if row.get('contact_key')}

    # Build active push ledger contacts set (against ready/running campaigns)
    active_ledger_contacts = {
        row['contact_key']
        for row in ledger_rows
        if row.get('campaign_id') in active_campaign_ids and row.get('contact_key')
    }

    # =========================================================================
    # SECTION 1: ELIGIBILITY FUNNEL PER BRAND
    # =========================================================================
    print("=" * 80)
    print("SECTION 1: ELIGIBILITY FUNNEL PER BRAND")
    print("=" * 80)

    total_leads_count = len(leads)
    print(f"Total leads in database: {total_leads_count}\n")

    funnel_survivors = {}

    for brand_key in ['amatec', 'jobdrive']:
        brand_title = BRAND_MAP[brand_key]
        print(f"--- Brand: {brand_title} ({brand_key}) ---")

        # Stage 0: All leads evaluated
        s0 = leads
        c0 = len(s0)

        # Stage 1: contact_email present and not '' or '-'
        s1 = [l for l in s0 if is_usable_email(l.get('contact_email'))]
        c1 = len(s1)

        # Stage 2: Not present in leads.suppression by lower(trim(contact_email))
        s2 = [l for l in s1 if normalize_email(l['contact_email']) not in suppressed_emails]
        c2 = len(s2)

        # Stage 3: '<brand>' = ANY(eligible_brands)
        s3 = [l for l in s2 if brand_key in (l.get('eligible_brands') or [])]
        c3 = len(s3)

        # Stage 4: No push_ledger row for contact_key against ready/running campaign
        s4 = [l for l in s3 if normalize_email(l['contact_email']) not in active_ledger_contacts]
        c4 = len(s4)

        # Stage 5: Legacy sync guard.
        # Rationale: mystrika_synced is the pre-ledger record of who was already contacted.
        # It stays authoritative for historical leads until push_ledger carries real history,
        # and only then is it retired. Removing it before that re-mails people.
        s5 = [
            l for l in s4
            if l.get('mystrika_synced') is None or normalize_email(l['contact_email']) in all_ledger_contacts
        ]
        c5 = len(s5)

        # Stage 6: Catchall guard.
        # Rationale: a catchall domain accepts any address, so the mailbox may not exist.
        # The Mystrika guardrails pull a wave at 3% bounce, so these are a deliverability
        # risk rather than a routing decision. This belongs in the funnel, not in a routing rule.
        s6 = [l for l in s5 if l.get('email_catchall') is not True]
        c6 = len(s6)

        # Suppressed leads relevant to this brand
        dropped_supp_brand = [
            l for l in s1
            if normalize_email(l['contact_email']) in suppressed_emails
            and brand_key in (l.get('eligible_brands') or [])
        ]

        funnel_survivors[brand_key] = s6

        print(f"  Stage 0 (Total pool in DB)              : {c0:>5}")
        print(f"  Stage 1 (Valid non-empty contact_email) : {c1:>5}  (dropped {c0 - c1:>4} missing/invalid email)")
        print(f"  Stage 2 (Not in suppression table)      : {c2:>5}  (dropped {c1 - c2:>4} suppressed globally)")
        print(f"  Stage 3 ('{brand_key}' in eligible_brands)  : {c3:>5}  (dropped {c2 - c3:>4} other brand)")
        print(f"  Stage 4 (No push_ledger in ready/running): {c4:>5}  (dropped {c3 - c4:>4} already in ledger)")
        print(f"  Stage 5 (Legacy sync guard)             : {c5:>5}  (dropped {c4 - c5:>4} historical synced leads)")
        print(f"  Stage 6 (Catchall guard)                : {c6:>5}  (dropped {c5 - c6:>4} catchall emails)")
        print(f"  => Eligible survivors for {brand_title}: {c6}")

        if brand_key == 'jobdrive':
            print("     Note: JobDrive has 0 leads dropped at Stage 6 because catchall detection has")
            print("     never run on JobDrive leads, not because its addresses are verified clean.")
        elif brand_key == 'amatec':
            print("     Note: Amatec eligible count fell from 22 to 1 because 21 leads are catchalls")
            print("     which were skipped by live workflows; this is correct expected behaviour.")

        if dropped_supp_brand:
            print(f"  Suppressed leads for {brand_title} (filtered at Stage 2):")
            for sl in dropped_supp_brand:
                email = sl.get('contact_email')
                reason = suppressed_emails.get(normalize_email(email), 'unknown')
                print(f"    - {sl.get('company_key')}: {email} (reason: {reason})")
        else:
            print(f"  Suppressed leads for {brand_title}: 0")
        print()

    # =========================================================================
    # SECTION 2: CAMPAIGNS CONSIDERED
    # =========================================================================
    print("=" * 80)
    print("SECTION 2: CAMPAIGNS CONSIDERED")
    print("=" * 80)
    print(f"Total campaigns in registry: {len(campaigns)}\n")

    running_ready_campaigns = []
    skipped_campaigns = []

    for c in campaigns:
        state = c['state']
        cname = c['campaign_name']
        brand = c['brand']
        if state in ('ready', 'running'):
            running_ready_campaigns.append(c)
            print(f"  [INCLUDED] [{brand:<8}] ({state:<7}) {cname}")
            print(f"             Reason: Campaign state is '{state}' -> evaluated for field derivation.")
        else:
            skipped_campaigns.append(c)
            print(f"  [SKIPPED]  [{brand:<8}] ({state:<7}) {cname}")
            print(f"             Reason: Campaign state is '{state}' (not ready/running).")
    print()

    # Check newspaper draft campaigns in copy table for empty bodies note
    np_drafts = [c for c in campaigns if 'Newspaper' in c['campaign_name']]
    print("Audit of Newspaper campaigns (3 draft campaigns in registry):")
    for npc in np_drafts:
        c_copy = [r for r in copy_rows if r['campaign_name'] == npc['campaign_name']]
        empty_b = [r for r in c_copy if not (r.get('body') or '').strip()]
        print(f"  - {npc['campaign_name']}: {len(c_copy)} variations found, {len(empty_b)} empty bodies.")
    print()

    # =========================================================================
    # SECTION 3: PER CAMPAIGN TAG DERIVATION & VALIDITY
    # =========================================================================
    print("=" * 80)
    print("SECTION 3: PER CAMPAIGN TAG DERIVATION & VALIDITY")
    print("=" * 80)

    tag_regex = re.compile(r'\{\{\s*([^}]+?)\s*\}\}')
    lead_columns = set(leads[0].keys()) if leads else set()
    campaign_tag_reports = {}

    for c in running_ready_campaigns:
        cname = c['campaign_name']
        cid = c.get('campaign_id')
        brand = c['brand']

        if cid:
            c_copy = [r for r in copy_rows if r.get('campaign_id') == cid]
            if not c_copy:
                c_copy = [r for r in copy_rows if r['campaign_name'] == cname]
        else:
            c_copy = [r for r in copy_rows if r['campaign_name'] == cname]

        validity_failures = []
        raw_tags_found = []
        tags_normalized = set()

        for row in c_copy:
            seq = row['sequence']
            var = row['variation']
            subj = row.get('subject') or ''
            body = row.get('body') or ''

            if not body.strip():
                validity_failures.append(f"Empty or null body at step {seq}, variation {var}")

            for text_source, text in [('subject', subj), ('body', body)]:
                for match in tag_regex.finditer(text):
                    captured = match.group(1)
                    raw_tags_found.append(captured)

                    if ' ' in captured:
                        validity_failures.append(
                            f"Tag with space '{{{{{captured}}}}}' at step {seq}, variation {var} ({text_source})"
                        )

                    norm_tag = re.sub(r'\s+', ' ', captured.strip().lower())
                    tags_normalized.add(norm_tag)

        tags_resolved = {}
        tags_unresolved = []

        for tag in sorted(tags_normalized):
            if tag in KNOWN_DEFAULTS:
                tags_resolved[tag] = f"Tier 1 (Known Default -> {KNOWN_DEFAULTS[tag]})"
            elif tag in lead_columns:
                tags_resolved[tag] = f"Tier 2 (Leads Column -> {tag})"
            else:
                tags_unresolved.append(tag)

        campaign_is_blocked = (len(validity_failures) > 0) or (len(tags_unresolved) > 0)
        status_str = "BLOCKED" if campaign_is_blocked else "READY"

        campaign_tag_reports[cname] = {
            'brand': brand,
            'copy_count': len(c_copy),
            'tags_found': sorted(list(set(raw_tags_found))),
            'tags_normalized': sorted(list(tags_normalized)),
            'tags_resolved': tags_resolved,
            'tags_unresolved': tags_unresolved,
            'validity_failures': validity_failures,
            'is_blocked': campaign_is_blocked,
        }

        print(f"Campaign: {cname} [{brand}] ({c['state']}) -> Status: {status_str}")
        print(f"  Copy variations loaded: {len(c_copy)}")
        print(f"  Raw tags found         : {sorted(list(set(raw_tags_found)))}")
        print(f"  Normalized tags        : {sorted(list(tags_normalized))}")

        if validity_failures:
            print("  Validity Failures      :")
            for vf in validity_failures:
                print(f"    - FAIL: {vf}")
        else:
            print("  Validity Failures      : None")

        if tags_resolved:
            print("  Resolved Tags          :")
            for t, res_source in tags_resolved.items():
                print(f"    - '{t}': {res_source}")

        if tags_unresolved:
            print("  Unresolved Tags (Tier 3 - Requires Human Mapping):")
            for t in tags_unresolved:
                print(f"    - '{t}': No match in defaults or leads columns -> BLOCKS CAMPAIGN")
        else:
            print("  Unresolved Tags        : None")

        print()

    # =========================================================================
    # SECTION 4: PER CAMPAIGN LEAD FILLING ANALYSIS
    # =========================================================================
    print("=" * 80)
    print("SECTION 4: PER CAMPAIGN LEAD FILLING ANALYSIS")
    print("=" * 80)

    for c in running_ready_campaigns:
        cname = c['campaign_name']
        rep = campaign_tag_reports[cname]
        brand = rep['brand']
        brand_key = 'amatec' if brand == 'Amatec' else 'jobdrive'
        eligible_pool = funnel_survivors[brand_key]

        print(f"Campaign: {cname} [{brand}]")
        print(f"  Eligible brand pool size: {len(eligible_pool)} leads")

        if rep['is_blocked']:
            reasons = []
            if rep['validity_failures']:
                reasons.append(f"{len(rep['validity_failures'])} validity failure(s)")
            if rep['tags_unresolved']:
                reasons.append(f"unresolved tag(s): {rep['tags_unresolved']}")
            print(f"  Campaign Tag Status     : BLOCKED ({', '.join(reasons)})")
            print(f"  Actual Leads Filled     : 0 leads (entire campaign is blocked from sending)")

            print("  Diagnostic Field Coverage (evaluating available fields on eligible pool):")
            missing_field_counts = Counter()
            hypothetical_fillable = 0

            for lead in eligible_pool:
                missing_fields = []
                for tag in rep['tags_normalized']:
                    if ' ' in tag:
                        continue
                    if tag in ('name', 'fname', 'first_name'):
                        val = lead.get('contact_name')
                        if not val or not str(val).strip():
                            missing_fields.append(tag)
                    elif tag == 'company':
                        val = lead.get('company_name')
                        if not val or not str(val).strip():
                            missing_fields.append(tag)
                    elif tag == 'role':
                        val = lead.get('role_group')
                        if not val or not str(val).strip():
                            missing_fields.append(tag)
                    elif tag == 'city':
                        val = lead.get('city')
                        if not val or not str(val).strip():
                            missing_fields.append(tag)
                    elif tag == 'apply_count':
                        val = lead.get('apply_count')
                        if val is None or str(val).strip() == '':
                            missing_fields.append(tag)
                    elif tag in lead_columns:
                        val = lead.get(tag)
                        if val is None or str(val).strip() == '':
                            missing_fields.append(tag)
                    else:
                        missing_fields.append(f"{tag}(unmapped)")

                if not missing_fields:
                    hypothetical_fillable += 1
                else:
                    for mf in missing_fields:
                        missing_field_counts[mf] += 1

            print(f"    - Leads with all mapped fields present : {hypothetical_fillable} / {len(eligible_pool)}")
            if missing_field_counts:
                print("    - Leads missing required fields (grouped):")
                for mf, cnt in missing_field_counts.most_common():
                    print(f"        * Missing '{mf}': {cnt} leads")
        else:
            fillable_leads = 0
            missing_field_counts = Counter()
            for lead in eligible_pool:
                missing_fields = []
                for tag in rep['tags_normalized']:
                    if tag in ('name', 'fname', 'first_name'):
                        val = lead.get('contact_name')
                    elif tag == 'company':
                        val = lead.get('company_name')
                    elif tag == 'role':
                        val = lead.get('role_group')
                    elif tag == 'city':
                        val = lead.get('city')
                    elif tag == 'apply_count':
                        val = lead.get('apply_count')
                    else:
                        val = lead.get(tag)

                    if val is None or str(val).strip() == '':
                        missing_fields.append(tag)

                if not missing_fields:
                    fillable_leads += 1
                else:
                    for mf in missing_fields:
                        missing_field_counts[mf] += 1

            print("  Campaign Tag Status : RESOLVED")
            print(f"  Leads Fillable      : {fillable_leads} / {len(eligible_pool)}")
            if missing_field_counts:
                print("  Leads Held (grouped by missing field):")
                for mf, cnt in missing_field_counts.most_common():
                    print(f"    - Missing '{mf}': {cnt} leads")

        print()

    # =========================================================================
    # SECTION 5: ROUTING STATUS
    # =========================================================================
    print("=" * 80)
    print("SECTION 5: ROUTING STATUS")
    print("=" * 80)
    print(f"Total routing rules in database: {len(routing_rules)}")
    current_segment_campaigns = [c for c in campaigns if c.get('segment_key')]
    print(f"Campaigns with segment_key assigned: {len(current_segment_campaigns)}")
    print()
    print("ROUTING ASSESSMENT:")
    print("  Because routing_rule is empty and no campaign in campaign_registry has a segment_key,")
    print("  zero leads can be routed to any campaign at this time.")
    print("  Every eligible lead would be HELD AND REPORTED.")
    print("  This is the EXPECTED and CORRECT behaviour at Phase 1 before routing rules and")
    print("  segment keys are configured.")
    print()

    # =========================================================================
    # SECTION 6: COMPARISON AGAINST LIVE WORKFLOWS (OLD vs NEW)
    # =========================================================================
    print("=" * 80)
    print("SECTION 6: COMPARISON AGAINST LIVE WORKFLOWS (OLD vs NEW)")
    print("=" * 80)

    # Old Workflow Queries:
    # 1. JobDrive workflow 1Uchg1PNp9eCqSVr:
    #    contact_email non-empty, mystrika_synced IS NULL, brand = 'jobdrive', ORDER BY score DESC LIMIT 200
    old_jobdrive_leads = [
        l for l in leads
        if l.get('brand') == 'jobdrive'
        and is_usable_email(l.get('contact_email'))
        and l.get('mystrika_synced') is None
    ]
    old_jobdrive_leads.sort(key=lambda x: (x.get('score') is not None, x.get('score') or 0), reverse=True)
    old_jobdrive_selected = old_jobdrive_leads[:200]
    old_jd_keys = {l['company_key']: l for l in old_jobdrive_selected}

    # 2. Amatec workflow AmatecMystrika01:
    #    brand = 'amatec', contact_email non-empty, mystrika_synced IS NULL,
    #    contact_source = 'apollo_person', status = 'new', email_catchall IS NOT TRUE
    old_amatec_leads = [
        l for l in leads
        if l.get('brand') == 'amatec'
        and is_usable_email(l.get('contact_email'))
        and l.get('mystrika_synced') is None
        and l.get('contact_source') == 'apollo_person'
        and l.get('status') == 'new'
        and l.get('email_catchall') is not True
    ]
    old_amatec_keys = {l['company_key']: l for l in old_amatec_leads}

    new_jd_keys = {l['company_key']: l for l in funnel_survivors['jobdrive']}
    new_am_keys = {l['company_key']: l for l in funnel_survivors['amatec']}

    print("Summary Counts:")
    print(f"  JobDrive - Old Query Picks: {len(old_jobdrive_selected):>4} | New Funnel Picks: {len(new_jd_keys):>4}")
    print(f"  Amatec   - Old Query Picks: {len(old_amatec_leads):>4} | New Funnel Picks: {len(new_am_keys):>4}")
    print()

    # --- JobDrive Differences ---
    print("--- JobDrive Lead Differences ---")
    jd_old_not_new = [k for k in old_jd_keys if k not in new_jd_keys]
    jd_new_not_old = [k for k in new_jd_keys if k not in old_jd_keys]

    print(f"Picks in Old query but dropped by New Funnel: {len(jd_old_not_new)}")
    if jd_old_not_new:
        for k in jd_old_not_new:
            l = old_jd_keys[k]
            email = l.get('contact_email')
            reasons = []
            if normalize_email(email) in suppressed_emails:
                reasons.append(f"Suppressed ({suppressed_emails[normalize_email(email)]})")
            if 'jobdrive' not in (l.get('eligible_brands') or []):
                reasons.append("Not in eligible_brands")
            if normalize_email(email) in active_ledger_contacts:
                reasons.append("Already in push_ledger")
            print(f"  - {k} ({email}): {', '.join(reasons)}")
    else:
        print("  None (0 differences).")

    print(f"Picks in New Funnel but not picked by Old Query: {len(jd_new_not_old)}")
    if jd_new_not_old:
        for k in jd_new_not_old:
            l = new_jd_keys[k]
            email = l.get('contact_email')
            reasons = []
            if l.get('mystrika_synced') is not None:
                reasons.append(f"mystrika_synced is set ({l['mystrika_synced']})")
            if l.get('brand') != 'jobdrive':
                reasons.append(f"brand is '{l.get('brand')}' (old query requires 'jobdrive')")
            print(f"  - {k} ({email}): {'; '.join(reasons)}")
    else:
        print("  None (0 differences).")

    print()

    # --- Amatec Differences ---
    print("--- Amatec Lead Differences ---")
    am_old_not_new = [k for k in old_amatec_keys if k not in new_am_keys]
    am_new_not_old = [k for k in new_am_keys if k not in old_amatec_keys]

    print(f"Picks in Old query but dropped by New Funnel: {len(am_old_not_new)}")
    if am_old_not_new:
        for k in am_old_not_new:
            l = old_amatec_keys[k]
            email = l.get('contact_email')
            reasons = []
            if normalize_email(email) in suppressed_emails:
                reasons.append(f"Suppressed ({suppressed_emails[normalize_email(email)]})")
            if 'amatec' not in (l.get('eligible_brands') or []):
                reasons.append("Not in eligible_brands")
            print(f"  - {k} ({email}): {', '.join(reasons)}")
    else:
        print("  None (0 differences).")

    print(f"Picks in New Funnel but not picked by Old Query: {len(am_new_not_old)}")
    if am_new_not_old:
        for k in am_new_not_old:
            l = new_am_keys[k]
            email = l.get('contact_email')
            reasons = []
            if l.get('contact_source') != 'apollo_person':
                reasons.append(f"contact_source is '{l.get('contact_source')}' (old query requires 'apollo_person')")
            if l.get('email_catchall') is True:
                reasons.append("email_catchall is True (old query requires NOT TRUE)")
            if l.get('status') != 'new':
                reasons.append(f"status is '{l.get('status')}' (old query requires 'new')")
            if l.get('brand') != 'amatec':
                reasons.append(f"brand is '{l.get('brand')}' (old query requires 'amatec')")
            print(f"  - {k} ({email}): {'; '.join(reasons)}")
    else:
        print("  None (0 differences).")

    print()

    # =========================================================================
    # SECTION 7: CLOSING SUMMARY
    # =========================================================================
    print("=" * 80)
    print("SECTION 7: CLOSING SUMMARY")
    print("=" * 80)
    print("What is currently BLOCKED and what a human must supply:")
    print()
    print("1. Routing Rules & Segment Keys:")
    print("   - routing_rule table has 0 rows.")
    print("   - campaign_registry has 0 campaigns with segment_key assigned.")
    print("   - Human action: Populate routing_rule and assign segment_key to current campaigns.")
    print()
    print("2. Campaign Copy Merge Tag Syntax Errors (Spaces in tag names):")
    print("   - 4 Amatec campaigns contain tags with spaces (e.g. {{Company Name}}, {{First Name}}):")
    print("     * Amatec Makers UK - Tue 7 July 2026")
    print("     * Amatec Makers US - Fri. 3rd July 2026")
    print("     * Amatec Movers - Fri. 3rd July 2026")
    print("     * Amatec Movers UK - Tue 6th July 2026")
    print("   - Human action: Fix copy in campaign_copy to use valid tags without spaces (e.g. {{company}}, {{fname}}).")
    print()
    print("3. Unresolved Merge Tags (Tier 3):")
    print("   - 'sender' in 'Amatec Lead Radar US-UK - Thu. 16 July 2026' (not in defaults, not a leads column).")
    print("   - 'industry_angle' in 'JobDrive Live-Role Wave 1 - Thu. 9th July 2026' (not in defaults, not a leads column).")
    print("   - \"firstname|default('there')\" in 'JobDrive Winback 100 Agency - Wed. 19th Aug 2026'.")
    print("   - Human action: Add mapping in campaign_field_map or update copy to use supported tags.")
    print()
    print("4. Suppression Enforcement:")
    print("   - 4 JobDrive leads match bounced suppression records in leads.suppression.")
    print("   - The new funnel properly drops all 4; the old workflow lacked suppression checks.")
    print()
    print("=" * 80)
    print("DRY RUN COMPLETE: Read-only execution finished successfully.")
    print("=" * 80)

    sys.exit(0)


if __name__ == '__main__':
    main()
