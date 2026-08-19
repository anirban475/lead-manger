#!/usr/bin/env python3
"""
ACTION-006: Dedup, Re-advertisement Signal, and Writing to the Leads Database

Three-layer pipeline:
  Layer 1: Ad level hash dedup against leads_park.newspaper_ad_raw
  Layer 2: Within-run contact level collapsing (key on phone/email, never company name)
  Layer 3: Cross-run comparison against leads.leads (syndication vs re-advertisement)

Rules:
  - Layer 2 keys strictly on contact (phone/email), never company name.
  - Same edition date = syndication (union roles, do not increment times_seen, do not change score/tier).
  - Later edition date = re-advertisement (times_seen +1, score +15 capped at 100, tier = 'hot', union roles).
  - NULL last_seen_date treated as unknown: set date, do not award bonus.
  - status in leads is NEVER touched or overwritten.
"""

import os
import re
import sys
import json
import sqlite3
import hashlib
import argparse
import datetime
import subprocess
from collections import defaultdict

# Import extraction logic and filters from extract.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract import (
    PHONE_RE,
    EMAIL_RE,
    classify_candidate,
    extract_clean_ad_text,
    extract_roles,
    resolve_company_name,
    normalize_company_key,
    score_lead,
    HIRING_VERB_PATS,
    NEWS_PATS,
    STAFFING_PATS,
    GOV_PATS,
    EDU_PATS,
    ICP_PATS,
)


def get_phone_last10(val: str | None) -> str:
    if not val:
        return ""
    digits = re.sub(r"\D", "", str(val))
    return digits[-10:] if len(digits) >= 10 else digits


def get_email_lower(val: str | None) -> str:
    if not val:
        return ""
    return str(val).strip().lower()


def compute_ad_key(edition_key: str, edition_date: str, page_no: int, raw_ad_text: str) -> str:
    norm_text = re.sub(r"\s+", " ", raw_ad_text.strip().lower())
    raw = f"{edition_key}|{edition_date}|{page_no}|{norm_text}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def union_roles(roles_list_a: list[str], roles_list_b: list[str]) -> list[str]:
    seen = set()
    combined = []
    for r in list(roles_list_a) + list(roles_list_b):
        clean_r = r.strip()
        if clean_r and clean_r.lower() not in seen and clean_r != "(Not specified)":
            seen.add(clean_r.lower())
            combined.append(clean_r)
    return combined if combined else ["(Not specified)"]


def query_leads_park_ad_keys() -> set[str]:
    """Fetch existing ad_keys from leads_park.newspaper_ad_raw."""
    try:
        cmd = [
            "docker", "exec", "shared-postgres",
            "psql", "-U", "admin", "-d", "leads_park", "-Atc",
            "SELECT ad_key FROM newspaper_ad_raw;"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return set(line.strip() for line in res.stdout.splitlines() if line.strip())
    except Exception as e:
        print(f"[WARNING] Failed to fetch existing ad_keys from leads_park: {e}", file=sys.stderr)
        return set()


def query_existing_leads() -> list[dict]:
    """Fetch existing leads from leads.leads table."""
    try:
        query = """
        SELECT json_build_object(
            'company_key', company_key,
            'company_name', company_name,
            'contact_phone', contact_phone,
            'contact_email', contact_email,
            'role_titles', role_titles,
            'score', score,
            'tier', tier,
            'status', status,
            'times_seen', times_seen,
            'last_seen_date', last_seen_date,
            'posted_date', posted_date,
            'city', city,
            'industry', industry,
            'size', size,
            'job_urls', job_urls,
            'source_query', source_query,
            'brand', brand
        )
        FROM leads;
        """
        cmd = [
            "docker", "exec", "shared-postgres",
            "psql", "-U", "admin", "-d", "leads", "-Atc",
            query
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        leads = []
        for line in res.stdout.splitlines():
            line = line.strip()
            if line:
                leads.append(json.loads(line))
        return leads
    except Exception as e:
        print(f"[WARNING] Failed to fetch existing leads from PostgreSQL: {e}", file=sys.stderr)
        return []


def run_layer1_and_extract(db_path: str, existing_ad_keys: set[str]) -> tuple[list[dict], list[dict], int]:
    """
    Layer 1: Scans sweep.db, skips ads already in newspaper_ad_raw.
    Applies OCR parsing and extraction gates.
    Returns (qualified_ads, rejected_ads, ads_skipped_layer1).
    """
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT edition_key, paper, city, edition_date, weekday, page_no, full_text
            FROM page_scan
            WHERE full_text IS NOT NULL
            ORDER BY edition_date ASC, page_no ASC
            """
        )
        rows = cursor.fetchall()

    ads_skipped_layer1 = 0
    qualified_ads = []
    rejected_ads = []

    for r in rows:
        ed_key, paper, page_city, ed_date, wd, pno, text = r

        anchors = []
        for m in PHONE_RE.finditer(text):
            anchors.append((m.start(), m.end(), "phone", m.group(0)))
        for m in EMAIL_RE.finditer(text):
            if "timesofindia" not in m.group(0).lower() and "hindustantimes" not in m.group(0).lower():
                anchors.append((m.start(), m.end(), "email", m.group(0)))
        anchors.sort()

        clusters = []
        for a in anchors:
            if not clusters:
                clusters.append([a])
            else:
                prev_end = clusters[-1][-1][1]
                if a[0] - prev_end <= 120:
                    clusters[-1].append(a)
                else:
                    clusters.append([a])

        for i, cl in enumerate(clusters):
            min_s = min(a[0] for a in cl)
            max_e = max(a[1] for a in cl)

            prev_e = clusters[i-1][-1][1] if i > 0 else 0
            next_s = clusters[i+1][0][0] if i < len(clusters)-1 else len(text)

            ad_text = extract_clean_ad_text(text, min_s, max_e, prev_e, next_s)
            ad_key = compute_ad_key(ed_key, ed_date, pno, ad_text)

            if ad_key in existing_ad_keys:
                ads_skipped_layer1 += 1
                continue

            cat, _, _, _ = classify_candidate(ad_text)
            if cat != "recruitment":
                rejected_ads.append({
                    "ad_key": ad_key,
                    "edition_key": ed_key,
                    "edition_date": ed_date,
                    "page_no": pno,
                    "ad_text": ad_text,
                    "outcome": "rejected",
                    "reject_reason": "other"
                })
                continue

            phones = [a[3] for a in cl if a[2] == "phone"]
            emails = [a[3] for a in cl if a[2] == "email"]

            phone = phones[0] if phones else None
            email = emails[0] if emails else None

            if not phone and not email:
                rejected_ads.append({
                    "ad_key": ad_key,
                    "edition_key": ed_key,
                    "edition_date": ed_date,
                    "page_no": pno,
                    "ad_text": ad_text,
                    "outcome": "rejected",
                    "reject_reason": "no_contact"
                })
                continue

            if not any(p.search(ad_text) for p in HIRING_VERB_PATS):
                rejected_ads.append({
                    "ad_key": ad_key,
                    "edition_key": ed_key,
                    "edition_date": ed_date,
                    "page_no": pno,
                    "ad_text": ad_text,
                    "outcome": "rejected",
                    "reject_reason": "other"
                })
                continue

            if any(p.search(ad_text) for p in NEWS_PATS) and not any(p.search(ad_text) for p in STAFFING_PATS):
                rejected_ads.append({
                    "ad_key": ad_key,
                    "edition_key": ed_key,
                    "edition_date": ed_date,
                    "page_no": pno,
                    "ad_text": ad_text,
                    "outcome": "rejected",
                    "reject_reason": "other"
                })
                continue

            if any(p.search(ad_text) for p in GOV_PATS):
                rejected_ads.append({
                    "ad_key": ad_key,
                    "edition_key": ed_key,
                    "edition_date": ed_date,
                    "page_no": pno,
                    "ad_text": ad_text,
                    "outcome": "rejected",
                    "reject_reason": "government"
                })
                continue

            if any(p.search(ad_text) for p in EDU_PATS):
                rejected_ads.append({
                    "ad_key": ad_key,
                    "edition_key": ed_key,
                    "edition_date": ed_date,
                    "page_no": pno,
                    "ad_text": ad_text,
                    "outcome": "rejected",
                    "reject_reason": "coaching_centre"
                })
                continue

            if any(p.search(ad_text) for p in STAFFING_PATS) or re.search(r"\b(?:1000\+|5000\+|fortune\s*500)\b", ad_text, re.IGNORECASE):
                rejected_ads.append({
                    "ad_key": ad_key,
                    "edition_key": ed_key,
                    "edition_date": ed_date,
                    "page_no": pno,
                    "ad_text": ad_text,
                    "outcome": "rejected",
                    "reject_reason": "enterprise"
                })
                continue

            roles = extract_roles(ad_text)
            comp_name, source = resolve_company_name(ad_text, email)
            is_icp = bool(any(p.search(ad_text) for p in ICP_PATS))
            score, tier = score_lead(ad_text, roles, phone, email, is_icp)

            if tier == "drop":
                rejected_ads.append({
                    "ad_key": ad_key,
                    "edition_key": ed_key,
                    "edition_date": ed_date,
                    "page_no": pno,
                    "ad_text": ad_text,
                    "outcome": "rejected",
                    "reject_reason": "low_score",
                    "score": score
                })
                continue

            comp_key = normalize_company_key(comp_name)
            if not comp_key:
                contact_seed = get_phone_last10(phone) or get_email_lower(email)
                comp_key = f"npc_{hashlib.sha1(contact_seed.encode('utf-8')).hexdigest()[:16]}"

            qualified_ads.append({
                "ad_key": ad_key,
                "edition_key": ed_key,
                "paper": paper,
                "city": page_city,
                "edition_date": ed_date,
                "weekday": wd,
                "page_no": pno,
                "company_name": comp_name,
                "company_key": comp_key,
                "company_source": source,
                "contact_phone": phone,
                "contact_email": email,
                "role_titles": roles if roles else ["(Not specified)"],
                "score": score,
                "tier": tier,
                "is_icp": is_icp,
                "raw_ad_text": ad_text
            })

    return qualified_ads, rejected_ads, ads_skipped_layer1


def run_layer2_contact_collapse(qualified_ads: list[dict]) -> tuple[list[dict], int, int]:
    """
    Layer 2: Within a run, collapse ads sharing phone or email.
    Keys strictly on contact (phone / email), NEVER on company name.
    Preserves highest scoring instance and unions role titles.
    Returns (collapsed_leads, same_date_syndication_count, genuine_duplicates_count).
    """
    phone_to_group = {}
    email_to_group = {}
    groups = []  # list of lists of ads

    for ad in qualified_ads:
        p10 = get_phone_last10(ad["contact_phone"])
        em = get_email_lower(ad["contact_email"])

        matched_group_indices = set()
        if p10 and p10 in phone_to_group:
            matched_group_indices.add(phone_to_group[p10])
        if em and em in email_to_group:
            matched_group_indices.add(email_to_group[em])

        if not matched_group_indices:
            new_idx = len(groups)
            groups.append([ad])
            if p10:
                phone_to_group[p10] = new_idx
            if em:
                email_to_group[em] = new_idx
        elif len(matched_group_indices) == 1:
            target_idx = list(matched_group_indices)[0]
            groups[target_idx].append(ad)
            if p10:
                phone_to_group[p10] = target_idx
            if em:
                email_to_group[em] = target_idx
        else:
            target_idx = min(matched_group_indices)
            merged = []
            for g_idx in sorted(matched_group_indices):
                merged.extend(groups[g_idx])
                groups[g_idx] = []
            merged.append(ad)
            groups[target_idx] = merged
            for a in merged:
                p_sub = get_phone_last10(a["contact_phone"])
                em_sub = get_email_lower(a["contact_email"])
                if p_sub:
                    phone_to_group[p_sub] = target_idx
                if em_sub:
                    email_to_group[em_sub] = target_idx

    active_groups = [g for g in groups if g]

    same_date_syndication_count = 0
    genuine_duplicates_count = 0
    collapsed_leads = []

    for g in active_groups:
        if len(g) > 1:
            date_editions = defaultdict(set)
            for ad in g:
                date_editions[ad["edition_date"]].add(ad["edition_key"])

            for dt, eds in date_editions.items():
                if len(eds) > 1:
                    same_date_syndication_count += (len(eds) - 1)
                ads_on_date = sum(1 for ad in g if ad["edition_date"] == dt)
                if ads_on_date > len(eds):
                    genuine_duplicates_count += (ads_on_date - len(eds))

        # Sort instances by score DESC, then latest edition_date DESC, then most roles
        sorted_instances = sorted(
            g,
            key=lambda x: (x["score"], x["edition_date"], len(x["role_titles"])),
            reverse=True
        )
        primary = sorted_instances[0]

        all_roles = []
        for ad in g:
            all_roles.extend(ad["role_titles"])
        combined_roles = union_roles([], all_roles)

        max_score = max(ad["score"] for ad in g)
        latest_date = max(ad["edition_date"] for ad in g)
        tier = "hot" if max_score >= 70 else "warm"

        collapsed_lead = dict(primary)
        collapsed_lead["role_titles"] = combined_roles
        collapsed_lead["score"] = max_score
        collapsed_lead["tier"] = tier
        collapsed_lead["edition_date"] = latest_date
        collapsed_lead["all_ad_keys"] = [ad["ad_key"] for ad in g]
        collapsed_lead["all_instances"] = g

        collapsed_leads.append(collapsed_lead)

    return collapsed_leads, same_date_syndication_count, genuine_duplicates_count


def run_layer3_cross_run_dedup(collapsed_leads: list[dict], existing_leads: list[dict]) -> tuple[list[dict], dict]:
    """
    Layer 3: Comparison against existing leads in PostgreSQL.
    Look up by contact_phone (last 10 digits), contact_email, or company_key.
    Branch:
      - No match: new lead (times_seen=1, last_seen_date=edition_date)
      - Match, last_seen_date is NULL: treat as unknown, set date, do not award bonus
      - Match, same last_seen_date: syndication (union roles, leave times_seen & score/tier untouched)
      - Match, later last_seen_date: re-advertisement (times_seen +1, score = min(100, score + 15), tier='hot', union roles)
      - status is NEVER touched
    """
    phone_map = {}
    email_map = {}
    key_map = {}

    for row in existing_leads:
        p10 = get_phone_last10(row.get("contact_phone"))
        em = get_email_lower(row.get("contact_email"))
        ckey = row.get("company_key")

        if p10:
            phone_map[p10] = row
        if em:
            email_map[em] = row
        if ckey:
            key_map[ckey] = row

    stats = {
        "new": 0,
        "syndication": 0,
        "readvertisement": 0,
        "touched_keys": []
    }

    final_payload_rows = []

    for lead in collapsed_leads:
        p10 = get_phone_last10(lead["contact_phone"])
        em = get_email_lower(lead["contact_email"])
        ckey = lead["company_key"]

        matched_lead = None
        if p10 and p10 in phone_map:
            matched_lead = phone_map[p10]
        elif em and em in email_map:
            matched_lead = email_map[em]
        elif ckey and ckey in key_map:
            matched_lead = key_map[ckey]

        batch_date = lead["edition_date"]

        if not matched_lead:
            # Case 1: Brand new lead
            stats["new"] += 1
            times_seen = 1
            last_seen_date = batch_date
            score = lead["score"]
            tier = lead["tier"]
            role_titles = lead["role_titles"]
            target_key = lead["company_key"]

            row_payload = build_save_leads_bulk_row(
                lead, target_key, role_titles, batch_date, score, tier
            )
            final_payload_rows.append({
                "payload": row_payload,
                "layer3_outcome": "new",
                "times_seen": times_seen,
                "last_seen_date": last_seen_date,
                "matched_company_key": None
            })
        else:
            # Matched existing lead
            target_key = matched_lead["company_key"]
            stats["touched_keys"].append(target_key)

            existing_last_seen = matched_lead.get("last_seen_date")
            existing_times_seen = matched_lead.get("times_seen") or 1
            existing_score = matched_lead.get("score") or lead["score"]
            existing_tier = matched_lead.get("tier") or lead["tier"]
            existing_roles = matched_lead.get("role_titles") or []

            combined_roles = union_roles(existing_roles, lead["role_titles"])

            if not existing_last_seen:
                # NULL last_seen_date: treat as unknown, set date, no bonus
                stats["syndication"] += 1
                times_seen = existing_times_seen
                last_seen_date = batch_date
                score = existing_score
                tier = existing_tier
                outcome = "syndication_merge"
            elif batch_date <= str(existing_last_seen):
                # Same date syndication
                stats["syndication"] += 1
                times_seen = existing_times_seen
                last_seen_date = str(existing_last_seen)
                score = existing_score
                tier = existing_tier
                outcome = "syndication"
            else:
                # Later date = Re-advertisement
                stats["readvertisement"] += 1
                times_seen = existing_times_seen + 1
                last_seen_date = batch_date
                score = min(100, existing_score + 15)
                tier = "hot"
                outcome = "readvertisement"

            row_payload = build_save_leads_bulk_row(
                lead, target_key, combined_roles, last_seen_date, score, tier
            )
            if matched_lead.get("company_name"):
                row_payload["company_name"] = matched_lead["company_name"]

            final_payload_rows.append({
                "payload": row_payload,
                "layer3_outcome": outcome,
                "times_seen": times_seen,
                "last_seen_date": last_seen_date,
                "matched_company_key": target_key
            })

    return final_payload_rows, stats


def build_save_leads_bulk_row(lead: dict, company_key: str, role_titles: list[str], posted_date: str, score: int, tier: str) -> dict:
    """Builds a single object matching the exact 23 fields for save_leads_bulk."""
    return {
        "company_key": company_key,
        "company_name": lead.get("company_name") or "",
        "industry": lead.get("industry") or "",
        "size": lead.get("size") or "",
        "city": lead.get("city") or "",
        "roles_count": str(len(role_titles)),
        "role_titles": "|".join(role_titles),
        "posted_date": str(posted_date),
        "job_urls": "",
        "contact_phone": lead.get("contact_phone") or "",
        "contact_email": lead.get("contact_email") or "",
        "contact_source": "newspaper",
        "company_website": lead.get("company_website") or "",
        "score": str(score),
        "tier": str(tier),
        "source_query": f"newspaper | {lead.get('edition_key', '')}",
        "apply_count": "",
        "role_group": "",
        "industry_label": "",
        "contact_name": "",
        "contact_title": "",
        "contact_linkedin": "",
        "brand": "jobdrive"
    }


def execute_step4_dry_run(db_path: str):
    """Executes Step 4 dry run and prints exact required output."""
    existing_ad_keys = query_leads_park_ad_keys()
    existing_leads = query_existing_leads()

    qualified_ads, rejected_ads, ads_skipped_layer1 = run_layer1_and_extract(db_path, existing_ad_keys)
    collapsed_leads, same_date_syndication, genuine_duplicates = run_layer2_contact_collapse(qualified_ads)
    final_payload_rows, layer3_stats = run_layer3_cross_run_dedup(collapsed_leads, existing_leads)

    print("==================================================")
    print("ACTION-006: STEP 4 DRY RUN REPORT")
    print("==================================================")
    print(f"1. Layer 1 Ad-Level Dedup:")
    print(f"   - Ads skipped at Layer 1 (already in newspaper_ad_raw): {ads_skipped_layer1}")
    print(f"   - Ads processed: {len(qualified_ads) + len(rejected_ads)}")
    print(f"   - Qualified ads entering Layer 2: {len(qualified_ads)}")
    print(f"   - Rejected ads: {len(rejected_ads)}")

    print(f"\n2. Layer 2 Within-Run Contact Collapsing:")
    print(f"   - Collapsed leads count: {len(collapsed_leads)}")
    print(f"   - Same-date syndication collapsed: {same_date_syndication}")
    print(f"   - Genuine duplicate ads collapsed: {genuine_duplicates}")

    print(f"\n3. Layer 3 Cross-Run Dedup Outcomes:")
    print(f"   - New leads to insert: {layer3_stats['new']}")
    print(f"   - Syndication matches (same date / unknown): {layer3_stats['syndication']}")
    print(f"   - Re-advertisements (later date repeat -> HOT +15): {layer3_stats['readvertisement']}")

    print(f"\n4. Existing leads touched ({len(layer3_stats['touched_keys'])} rows):")
    for k in sorted(set(layer3_stats["touched_keys"])):
        print(f"   - {k}")

    raw_payloads = [item["payload"] for item in final_payload_rows]
    print(f"\n5. Exact JSON for save_leads_bulk (First 3 rows in full):")
    print(json.dumps(raw_payloads[:3], indent=2))
    print("\n[DRY RUN COMPLETE] Zero database writes performed.")


def main():
    parser = argparse.ArgumentParser(description="ACTION-006 Newspaper Dedup & Re-advertisement Runner")
    parser.add_argument("--db", type=str, default="/root/newspaper_sweep/sweep.db", help="Path to SQLite sweep database")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Perform dry run without database writes")
    args = parser.parse_args()

    execute_step4_dry_run(args.db)


if __name__ == "__main__":
    main()
