#!/usr/bin/env python3
"""
ACTION-006 / ACTION-011: Dedup, Re-advertisement Signal, and Writing to the Leads Database

Three-layer pipeline:
  Layer 1: Ad level hash dedup against leads_park.newspaper_ad_raw
  Layer 2: Within-run contact level collapsing on (contact, edition_date)
  Layer 3: Cross-run comparison against leads.leads (syndication vs re-advertisement)

Rules:
  - Layer 2 keys strictly on (contact, edition_date), never company name alone or collapsing across dates.
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
    extract_location,
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
            'edition_city', edition_city,
            'job_description', job_description,
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

            extracted_loc = extract_location(ad_text)
            city = extracted_loc if extracted_loc else page_city
            edition_city = page_city

            qualified_ads.append({
                "ad_key": ad_key,
                "edition_key": ed_key,
                "paper": paper,
                "city": city,
                "edition_city": edition_city,
                "extracted_city": extracted_loc,
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
    Layer 2: Within a run, collapse ads sharing phone or email ON THE SAME EDITION DATE.
    Keys strictly on (contact, edition_date), NEVER on company name alone, and NEVER across dates.
    Preserves highest scoring instance and unions role titles.
    Returns (collapsed_leads, same_date_syndication_count, genuine_duplicates_count).
    """
    phone_date_to_group = {}
    email_date_to_group = {}
    groups = []  # list of lists of ads

    for ad in qualified_ads:
        ed_date = ad["edition_date"]
        p10 = get_phone_last10(ad["contact_phone"])
        em = get_email_lower(ad["contact_email"])

        p_key = (p10, ed_date) if p10 else None
        e_key = (em, ed_date) if em else None

        matched_group_indices = set()
        if p_key and p_key in phone_date_to_group:
            matched_group_indices.add(phone_date_to_group[p_key])
        if e_key and e_key in email_date_to_group:
            matched_group_indices.add(email_date_to_group[e_key])

        if not matched_group_indices:
            new_idx = len(groups)
            groups.append([ad])
            if p_key:
                phone_date_to_group[p_key] = new_idx
            if e_key:
                email_date_to_group[e_key] = new_idx
        elif len(matched_group_indices) == 1:
            target_idx = list(matched_group_indices)[0]
            groups[target_idx].append(ad)
            if p_key:
                phone_date_to_group[p_key] = target_idx
            if e_key:
                email_date_to_group[e_key] = target_idx
        else:
            target_idx = min(matched_group_indices)
            merged = []
            for g_idx in sorted(matched_group_indices):
                merged.extend(groups[g_idx])
                groups[g_idx] = []
            merged.append(ad)
            groups[target_idx] = merged
            for a in merged:
                a_dt = a["edition_date"]
                p_sub = get_phone_last10(a["contact_phone"])
                em_sub = get_email_lower(a["contact_email"])
                if p_sub:
                    phone_date_to_group[(p_sub, a_dt)] = target_idx
                if em_sub:
                    email_date_to_group[(em_sub, a_dt)] = target_idx

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

        # Aggregate unique job description texts
        seen_texts = set()
        ad_texts = []
        for ad in g:
            t = (ad.get("raw_ad_text") or "").strip()
            if t and t not in seen_texts:
                seen_texts.add(t)
                ad_texts.append(t)
        job_description = "\n\n".join(ad_texts)

        # Location extraction
        extracted_city = next((ad.get("extracted_city") for ad in g if ad.get("extracted_city")), None)
        edition_city = next((ad.get("edition_city") for ad in g if ad.get("edition_city")), primary.get("city"))
        city = extracted_city if extracted_city else edition_city

        collapsed_lead = dict(primary)
        collapsed_lead["role_titles"] = combined_roles
        collapsed_lead["score"] = max_score
        collapsed_lead["tier"] = tier
        collapsed_lead["city"] = city
        collapsed_lead["edition_city"] = edition_city
        collapsed_lead["job_description"] = job_description
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
            job_description = lead.get("job_description") or ""
            city = lead.get("city") or ""
            edition_city = lead.get("edition_city") or ""

            row_payload = build_save_leads_bulk_row(
                lead, target_key, role_titles, batch_date, score, tier, times_seen, last_seen_date,
                job_description=job_description, edition_city=edition_city, city=city
            )
            new_entry = {
                "company_key": target_key,
                "company_name": lead.get("company_name"),
                "contact_phone": lead.get("contact_phone"),
                "contact_email": lead.get("contact_email"),
                "role_titles": list(role_titles),
                "score": score,
                "tier": tier,
                "times_seen": times_seen,
                "last_seen_date": last_seen_date,
                "job_description": job_description,
                "city": city,
                "edition_city": edition_city
            }
            if p10:
                phone_map[p10] = new_entry
            if em:
                email_map[em] = new_entry
            key_map[target_key] = new_entry

            final_payload_rows.append({
                "payload": row_payload,
                "layer3_outcome": "new",
                "times_seen": times_seen,
                "last_seen_date": last_seen_date,
                "matched_company_key": None,
                "collapsed_lead": lead
            })
        else:
            # Matched existing lead
            target_key = matched_lead["company_key"]
            stats["touched_keys"].append(target_key)

            existing_last_seen = matched_lead.get("last_seen_date")
            existing_times_seen = matched_lead.get("times_seen") or 1
            existing_score = matched_lead.get("score") if matched_lead.get("score") is not None else lead["score"]
            existing_tier = matched_lead.get("tier") or lead["tier"]
            existing_roles = matched_lead.get("role_titles") or []

            combined_roles = union_roles(existing_roles, lead["role_titles"])

            # Combine job descriptions
            existing_jd = matched_lead.get("job_description") or ""
            new_jd = lead.get("job_description") or ""
            jd_parts = []
            seen_jd = set()
            for jd_str in [existing_jd, new_jd]:
                if jd_str:
                    for chunk in jd_str.split("\n\n"):
                        clean_chunk = chunk.strip()
                        if clean_chunk and clean_chunk not in seen_jd:
                            seen_jd.add(clean_chunk)
                            jd_parts.append(clean_chunk)
            combined_jd = "\n\n".join(jd_parts)

            # Location handling
            lead_city = lead.get("city")
            lead_ed_city = lead.get("edition_city")
            existing_city = matched_lead.get("city")
            existing_ed_city = matched_lead.get("edition_city") or lead_ed_city

            final_ed_city = existing_ed_city or lead_ed_city
            if lead.get("extracted_city"):
                final_city = lead.get("extracted_city")
            elif existing_city and existing_city.lower() != (existing_ed_city or "").lower():
                final_city = existing_city
            else:
                final_city = lead_city or existing_city or final_ed_city

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

            matched_lead["times_seen"] = times_seen
            matched_lead["last_seen_date"] = last_seen_date
            matched_lead["score"] = score
            matched_lead["tier"] = tier
            matched_lead["role_titles"] = combined_roles
            matched_lead["job_description"] = combined_jd
            matched_lead["city"] = final_city
            matched_lead["edition_city"] = final_ed_city

            row_payload = build_save_leads_bulk_row(
                lead, target_key, combined_roles, last_seen_date, score, tier, times_seen, last_seen_date,
                job_description=combined_jd, edition_city=final_ed_city, city=final_city
            )
            if matched_lead.get("company_name"):
                row_payload["company_name"] = matched_lead["company_name"]

            final_payload_rows.append({
                "payload": row_payload,
                "layer3_outcome": outcome,
                "times_seen": times_seen,
                "last_seen_date": last_seen_date,
                "matched_company_key": target_key,
                "collapsed_lead": lead
            })

    return final_payload_rows, stats


def build_save_leads_bulk_row(
    lead: dict, company_key: str, role_titles: list[str], posted_date: str,
    score: int, tier: str, times_seen: int = 1, last_seen_date: str | None = None,
    job_description: str = "", edition_city: str = "", city: str = ""
) -> dict:
    """Builds a single object matching the exact fields for save_leads_bulk and leads table."""
    return {
        "company_key": company_key,
        "company_name": lead.get("company_name") or "",
        "industry": lead.get("industry") or "",
        "size": lead.get("size") or "",
        "city": city or lead.get("city") or "",
        "edition_city": edition_city or lead.get("edition_city") or "",
        "job_description": job_description or lead.get("job_description") or "",
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
        "brand": "jobdrive",
        "times_seen": str(times_seen),
        "last_seen_date": str(last_seen_date) if last_seen_date else str(posted_date)
    }


def save_leads_to_db(payload_rows: list[dict]):
    """Upserts leads in batches into leads.leads."""
    if not payload_rows:
        return
    batch_size = 200
    for i in range(0, len(payload_rows), batch_size):
        batch = payload_rows[i:i + batch_size]
        json_data = json.dumps(batch)
        psql_query = f"""
INSERT INTO leads (
    company_key, company_name, industry, size, city, roles_count, role_titles,
    posted_date, job_urls, contact_phone, contact_email, contact_source,
    company_website, score, tier, source_query, apply_count, role_group,
    industry_label, contact_name, contact_title, contact_linkedin, brand,
    times_seen, last_seen_date, job_description, edition_city
)
SELECT DISTINCT ON (r.company_key)
    r.company_key, r.company_name, r.industry, r.size, r.city,
    NULLIF(r.roles_count,'')::int,
    CASE WHEN r.role_titles LIKE '%|%' THEN string_to_array(r.role_titles,'|') ELSE string_to_array(r.role_titles,',') END,
    NULLIF(r.posted_date,'')::date,
    string_to_array(r.job_urls,','),
    r.contact_phone, r.contact_email, r.contact_source, r.company_website,
    NULLIF(r.score,'')::int, r.tier, r.source_query,
    NULLIF(r.apply_count,'')::int,
    r.role_group, r.industry_label, r.contact_name, r.contact_title, r.contact_linkedin, r.brand,
    NULLIF(r.times_seen,'')::int,
    NULLIF(r.last_seen_date,'')::date,
    NULLIF(r.job_description, ''),
    NULLIF(r.edition_city, '')
FROM jsonb_to_recordset($${json_data}$$::jsonb) AS r(
    company_key text, company_name text, industry text, size text, city text,
    roles_count text, role_titles text, posted_date text, job_urls text,
    contact_phone text, contact_email text, contact_source text, company_website text,
    score text, tier text, source_query text, apply_count text, role_group text,
    industry_label text, contact_name text, contact_title text, contact_linkedin text, brand text,
    times_seen text, last_seen_date text, job_description text, edition_city text
)
ORDER BY r.company_key
ON CONFLICT (company_key) DO UPDATE SET
    city = COALESCE(NULLIF(EXCLUDED.city, ''), leads.city),
    edition_city = COALESCE(leads.edition_city, EXCLUDED.edition_city),
    job_description = COALESCE(EXCLUDED.job_description, leads.job_description),
    roles_count = EXCLUDED.roles_count,
    role_titles = EXCLUDED.role_titles,
    posted_date = EXCLUDED.posted_date,
    job_urls = EXCLUDED.job_urls,
    score = EXCLUDED.score,
    tier = EXCLUDED.tier,
    times_seen = EXCLUDED.times_seen,
    last_seen_date = EXCLUDED.last_seen_date,
    source_query = COALESCE(leads.source_query, EXCLUDED.source_query),
    apply_count = EXCLUDED.apply_count,
    role_group = EXCLUDED.role_group,
    industry_label = EXCLUDED.industry_label,
    contact_name = COALESCE(leads.contact_name, EXCLUDED.contact_name),
    contact_title = COALESCE(leads.contact_title, EXCLUDED.contact_title),
    contact_linkedin = COALESCE(leads.contact_linkedin, EXCLUDED.contact_linkedin),
    updated_at = now()
RETURNING company_key, status;
"""
        cmd = ["docker", "exec", "-i", "shared-postgres", "psql", "-U", "admin", "-d", "leads"]
        res = subprocess.run(cmd, input=psql_query, capture_output=True, text=True, check=True)


def save_newspaper_ads_raw_to_db(ad_rows: list[dict]):
    """Inserts processed ads in batches into leads_park.newspaper_ad_raw."""
    if not ad_rows:
        return
    batch_size = 200
    for i in range(0, len(ad_rows), batch_size):
        batch = ad_rows[i:i + batch_size]
        json_data = json.dumps(batch)
        psql_query = f"""
INSERT INTO newspaper_ad_raw (
    ad_key, run_date, brand, publication, page_url, ad_index, ad_text,
    parsed_company, parsed_city, parsed_phone, parsed_email, parsed_roles,
    outcome, reject_reason, score, company_key
)
SELECT
    r.ad_key,
    NULLIF(r.run_date, '')::date,
    r.brand,
    r.publication,
    r.page_url,
    NULLIF(r.ad_index, '')::int,
    r.ad_text,
    r.parsed_company,
    r.parsed_city,
    r.parsed_phone,
    r.parsed_email,
    CASE WHEN r.parsed_roles LIKE '%|%' THEN string_to_array(r.parsed_roles, '|') ELSE string_to_array(r.parsed_roles, ',') END,
    r.outcome,
    NULLIF(r.reject_reason, ''),
    NULLIF(r.score, '')::int,
    NULLIF(r.company_key, '')
FROM jsonb_to_recordset($${json_data}$$::jsonb) AS r(
    ad_key text, run_date text, brand text, publication text, page_url text,
    ad_index text, ad_text text, parsed_company text, parsed_city text,
    parsed_phone text, parsed_email text, parsed_roles text, outcome text,
    reject_reason text, score text, company_key text
)
ON CONFLICT (ad_key) DO NOTHING;
"""
        cmd = ["docker", "exec", "-i", "shared-postgres", "psql", "-U", "admin", "-d", "leads_park"]
        res = subprocess.run(cmd, input=psql_query, capture_output=True, text=True, check=True)


def execute_pipeline(db_path: str, write: bool = False):
    """Executes dedup and re-advertisement pipeline."""
    if write:
        print("[MODE: WRITE] Real database writes enabled.")
    else:
        print("[MODE: DRY-RUN] Zero database writes (read-only mode).")

    existing_ad_keys = query_leads_park_ad_keys()
    existing_leads = query_existing_leads()

    qualified_ads, rejected_ads, ads_skipped_layer1 = run_layer1_and_extract(db_path, existing_ad_keys)
    collapsed_leads, same_date_syndication, genuine_duplicates = run_layer2_contact_collapse(qualified_ads)
    final_payload_rows, layer3_stats = run_layer3_cross_run_dedup(collapsed_leads, existing_leads)

    print("==================================================")
    print("ACTION-006: DEDUP & RE-ADVERTISEMENT REPORT")
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

    unique_payloads_by_key = {}
    for item in final_payload_rows:
        unique_payloads_by_key[item["payload"]["company_key"]] = item["payload"]
    raw_payloads = list(unique_payloads_by_key.values())
    print(f"\n5. Exact JSON for save_leads_bulk (First 3 rows in full):")
    print(json.dumps(raw_payloads[:3], indent=2))

    if write:
        print("\nWriting leads to leads database...")
        save_leads_to_db(raw_payloads)

        raw_ad_records = []
        for item in final_payload_rows:
            target_ckey = item["payload"]["company_key"]
            c_lead = item.get("collapsed_lead", {})
            for ad in c_lead.get("all_instances", []):
                raw_ad_records.append({
                    "ad_key": ad["ad_key"],
                    "run_date": str(ad.get("edition_date") or datetime.date.today().isoformat()),
                    "brand": "jobdrive",
                    "publication": ad.get("paper") or ad.get("edition_key") or "",
                    "page_url": f"{ad.get('edition_key')}/{ad.get('edition_date')}/page_{ad.get('page_no')}",
                    "ad_index": str(ad.get("page_no") or 0),
                    "ad_text": ad.get("raw_ad_text") or "",
                    "parsed_company": ad.get("company_name") or "",
                    "parsed_city": ad.get("city") or "",
                    "parsed_phone": ad.get("contact_phone") or "",
                    "parsed_email": ad.get("contact_email") or "",
                    "parsed_roles": "|".join(ad.get("role_titles", [])),
                    "outcome": "saved",
                    "reject_reason": "",
                    "score": str(ad.get("score") or 0),
                    "company_key": target_ckey
                })

        for ad in rejected_ads:
            raw_ad_records.append({
                "ad_key": ad["ad_key"],
                "run_date": str(ad.get("edition_date") or datetime.date.today().isoformat()),
                "brand": "jobdrive",
                "publication": ad.get("edition_key") or "",
                "page_url": f"{ad.get('edition_key')}/{ad.get('edition_date')}/page_{ad.get('page_no')}",
                "ad_index": str(ad.get("page_no") or 0),
                "ad_text": ad.get("ad_text") or "",
                "parsed_company": "",
                "parsed_city": "",
                "parsed_phone": "",
                "parsed_email": "",
                "parsed_roles": "",
                "outcome": "rejected",
                "reject_reason": ad.get("reject_reason") or "other",
                "score": str(ad.get("score") or ""),
                "company_key": ""
            })

        print("Writing raw ads to leads_park database...")
        save_newspaper_ads_raw_to_db(raw_ad_records)
        print(f"\n[WRITE COMPLETE] Successfully written {len(raw_payloads)} leads and {len(raw_ad_records)} raw ads.")
    else:
        print("\n[DRY RUN COMPLETE] Zero database writes performed.")


def main():
    parser = argparse.ArgumentParser(description="ACTION-006 Newspaper Dedup & Re-advertisement Runner")
    parser.add_argument("--db", type=str, default="/root/newspaper_sweep/sweep.db", help="Path to SQLite sweep database")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", default=False, help="Perform dry run without database writes (default)")
    group.add_argument("--write", action="store_true", default=False, help="Perform real database writes")
    args = parser.parse_args()

    execute_pipeline(args.db, write=args.write)


if __name__ == "__main__":
    main()
