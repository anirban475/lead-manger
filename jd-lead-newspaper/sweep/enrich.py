#!/usr/bin/env python3
"""
ACTION-011 Part C: Apollo Enrichment for Email-Only Newspaper Leads

Enriches newspaper leads that carry an email but no phone number
by querying Apollo via the n8n MCP Server endpoint.

Hard Money Safeguards:
1. Dry run by default: --write must be passed explicitly to spend credits.
2. Hard cap per run: --max-credits defaults to 0 (unlimited) and stops when reached if specified.
3. Never re-enrich: skips leads with contact_source starting with 'apollo'.
4. Actual spend tracking: logs every credit consumed.
"""

import os
import re
import sys
import json
import argparse
import subprocess
import urllib.request
from typing import Optional, Dict, Any, List, Tuple

FREE_PROVIDERS = {
    'gmail.com', 'yahoo.com', 'yahoo.co.in', 'hotmail.com', 'rediffmail.com',
    'outlook.com', 'live.com', 'aol.com', 'icloud.com', 'mail.com', 'zoho.com',
    'ymail.com', 'protonmail.com', 'proton.me', 'msn.com'
}

DECISION_MAKER_TITLES = [
    'founder', 'co-founder', 'owner', 'proprietor', 'partner',
    'director', 'managing director', 'executive director', 'ceo',
    'general manager', 'president', 'vice president',
    'head of hr', 'hr manager', 'talent acquisition', 'human resources manager'
]


class ApolloMCPClient:
    def __init__(self, mcp_url: str = "http://localhost:5678/mcp/amatec-radar"):
        self.mcp_url = mcp_url
        self.session_id: Optional[str] = None
        self._initialize()

    def _post(self, payload: dict) -> Tuple[Optional[str], str]:
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/event-stream'
        }
        if self.session_id:
            headers['mcp-session-id'] = self.session_id

        req = urllib.request.Request(
            self.mcp_url,
            data=json.dumps(payload).encode('utf-8'),
            headers=headers
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            sid = resp.headers.get('mcp-session-id')
            body = resp.read().decode('utf-8')
            return sid, body

    def _initialize(self):
        sid, _ = self._post({
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'initialize',
            'params': {
                'protocolVersion': '2024-11-05',
                'capabilities': {},
                'clientInfo': {'name': 'enrich-py', 'version': '1.0.0'}
            }
        })
        self.session_id = sid
        self._post({
            'jsonrpc': '2.0',
            'method': 'notifications/initialized'
        })

    def search_people(self, domain: Optional[str] = None, company_name: Optional[str] = None, per_page: int = 5) -> List[dict]:
        """Free Apollo candidate search via people_search (0 credits)."""
        search_body: Dict[str, Any] = {'per_page': per_page}
        if domain:
            search_body['q_organization_domains'] = domain
        elif company_name:
            search_body['q_organization_name'] = company_name
        else:
            return []

        _, resp_text = self._post({
            'jsonrpc': '2.0',
            'id': 2,
            'method': 'tools/call',
            'params': {
                'name': 'people_search',
                'arguments': {
                    'inputJson': json.dumps(search_body)
                }
            }
        })

        people = []
        for line in resp_text.splitlines():
            if line.startswith('data: '):
                try:
                    res_json = json.loads(line[6:])
                    content = res_json['result']['content'][0]['text']
                    parsed = json.loads(content)
                    if isinstance(parsed, list) and parsed:
                        people = parsed[0].get('people', [])
                    elif isinstance(parsed, dict):
                        people = parsed.get('people', [])
                except Exception as e:
                    print(f"[WARN] Failed to parse search response: {e}", file=sys.stderr)
        return people

    def reveal_person(self, person_id: str) -> List[dict]:
        """Paid Apollo person reveal via reveal_emails (1 credit per match)."""
        _, resp_text = self._post({
            'jsonrpc': '2.0',
            'id': 3,
            'method': 'tools/call',
            'params': {
                'name': 'reveal_emails',
                'arguments': {
                    'personIds': json.dumps([person_id])
                }
            }
        })

        matches = []
        for line in resp_text.splitlines():
            if line.startswith('data: '):
                try:
                    res_json = json.loads(line[6:])
                    content = res_json['result']['content'][0]['text']
                    parsed = json.loads(content)
                    if isinstance(parsed, list) and parsed:
                        matches = parsed[0].get('matches', [])
                    elif isinstance(parsed, dict):
                        matches = parsed.get('matches', [])
                except Exception as e:
                    print(f"[WARN] Failed to parse reveal response: {e}", file=sys.stderr)
        return matches


def query_target_leads() -> List[dict]:
    """Fetch target leads: brand=jobdrive, np%, email not null, phone < 8 digits, not already apollo enriched."""
    query = """
    SELECT json_build_object(
        'company_key', company_key,
        'company_name', company_name,
        'contact_email', contact_email,
        'contact_phone', contact_phone,
        'contact_source', contact_source,
        'company_website', company_website
    )
    FROM leads
    WHERE brand = 'jobdrive'
      AND company_key LIKE 'np%'
      AND contact_email IS NOT NULL AND contact_email != ''
      AND (contact_phone IS NULL OR length(regexp_replace(contact_phone, '[^0-9]', '', 'g')) < 8)
      AND (contact_source IS NULL OR NOT contact_source LIKE 'apollo%')
    ORDER BY company_key;
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


def sanitize_phone(phone_val: Any) -> Optional[str]:
    if not phone_val:
        return None
    digits = re.sub(r'\D', '', str(phone_val))
    if len(digits) >= 8:
        return str(phone_val).strip()
    return None


def select_best_candidate(people: List[dict]) -> Optional[dict]:
    """Select best decision maker candidate from Apollo search results."""
    if not people:
        return None

    # Score candidates by title relevance
    scored = []
    for p in people:
        title = (p.get('title') or '').lower()
        has_email = bool(p.get('has_email'))
        score = 0
        for i, target in enumerate(DECISION_MAKER_TITLES):
            if target in title:
                score += (100 - i * 5)
                break
        if has_email:
            score += 20
        scored.append((score, p))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1] if scored else None


def update_lead_in_db(company_key: str, phone: Optional[str], source: str, contact_name: Optional[str] = None, contact_title: Optional[str] = None):
    """Updates lead with phone number and contact_source. NEVER touches status."""
    row_json = json.dumps({
        'company_key': company_key,
        'contact_phone': phone or '',
        'contact_source': source,
        'contact_name': contact_name or '',
        'contact_title': contact_title or ''
    })
    
    sql = f"""
    UPDATE leads AS l
    SET contact_phone = CASE WHEN r.contact_phone != '' THEN r.contact_phone ELSE l.contact_phone END,
        contact_source = r.contact_source,
        contact_name = CASE WHEN r.contact_name != '' THEN r.contact_name ELSE l.contact_name END,
        contact_title = CASE WHEN r.contact_title != '' THEN r.contact_title ELSE l.contact_title END,
        updated_at = now()
    FROM jsonb_to_record(CAST('{row_json.replace("'", "''")}' AS jsonb)) AS r(
        company_key text, contact_phone text, contact_source text, contact_name text, contact_title text
    )
    WHERE l.company_key = r.company_key;
    """
    cmd = ["docker", "exec", "-i", "shared-postgres", "psql", "-U", "admin", "-d", "leads"]
    subprocess.run(cmd, input=sql, capture_output=True, text=True, check=True)


def run_enrichment(write: bool = False, max_credits: int = 0, mcp_url: str = "http://localhost:5678/mcp/amatec-radar"):
    mode_str = "[MODE: WRITE] Real Apollo reveals enabled." if write else "[MODE: DRY-RUN] Zero credits will be spent."
    cap_str = f"{max_credits} credits maximum" if max_credits > 0 else "no cap"
    print("==================================================")
    print("ACTION-011 PART C: APOLLO LEAD ENRICHMENT")
    print(mode_str)
    print(f"Hard Cap: {cap_str}")
    print("==================================================")

    leads = query_target_leads()
    print(f"\n1. Target set identified: {len(leads)} leads (email present, phone < 8 digits, not previously attempted)")

    client = ApolloMCPClient(mcp_url=mcp_url)

    credits_spent = 0
    direct_phones_found = 0
    org_phones_found = 0
    no_phone_found = 0
    not_indexed_count = 0

    results = []

    for i, lead in enumerate(leads, 1):
        if max_credits > 0 and credits_spent >= max_credits:
            print(f"\n[HARD CAP REACHED] Stopped at {credits_spent}/{max_credits} credits.")
            break

        ck = lead['company_key']
        comp_name = lead.get('company_name') or ''
        email = (lead.get('contact_email') or '').strip().lower()
        domain = email.split('@')[-1] if ('@' in email and email.split('@')[-1] not in FREE_PROVIDERS) else None

        # 1. Search candidate (FREE, 0 credits)
        people = client.search_people(domain=domain, company_name=comp_name if not domain else None)
        
        if not people:
            not_indexed_count += 1
            results.append({
                'company_key': ck,
                'email': email,
                'domain': domain,
                'status': 'not_indexed',
                'credits': 0
            })
            if write:
                update_lead_in_db(ck, phone=None, source='apollo_none')
            continue

        best_person = select_best_candidate(people)
        person_id = best_person.get('id') if best_person else None

        if not person_id:
            not_indexed_count += 1
            results.append({
                'company_key': ck,
                'email': email,
                'domain': domain,
                'status': 'no_person_id',
                'credits': 0
            })
            if write:
                update_lead_in_db(ck, phone=None, source='apollo_none')
            continue

        # Candidate found
        if not write:
            # DRY RUN: Estimate spend, do not call reveal
            credits_spent += 1
            results.append({
                'company_key': ck,
                'email': email,
                'domain': domain,
                'candidate_title': best_person.get('title'),
                'candidate_id': person_id,
                'status': 'dry_run_match',
                'credits': 1
            })
        else:
            # REAL WRITE: Spend credit on reveal
            credits_spent += 1
            matches = client.reveal_person(person_id)
            matched_person = matches[0] if matches else {}
            
            # Extract phone
            phone_found = None
            source_type = 'apollo_none'
            
            # Check person direct phones
            p_phones = matched_person.get('phone_numbers') or []
            for ph in p_phones:
                s_ph = sanitize_phone(ph.get('sanitized_number') or ph.get('raw_number'))
                if s_ph:
                    phone_found = s_ph
                    source_type = 'apollo_person'
                    break
                    
            if not phone_found and matched_person.get('phone_number'):
                phone_found = sanitize_phone(matched_person.get('phone_number'))
                if phone_found:
                    source_type = 'apollo_person'
                    
            # Fallback to org phone
            if not phone_found:
                org = matched_person.get('organization') or {}
                org_phone = sanitize_phone(org.get('phone'))
                if org_phone:
                    phone_found = org_phone
                    source_type = 'apollo_org'

            c_name = matched_person.get('name')
            c_title = matched_person.get('title')

            if source_type == 'apollo_person':
                direct_phones_found += 1
            elif source_type == 'apollo_org':
                org_phones_found += 1
            else:
                no_phone_found += 1

            update_lead_in_db(ck, phone=phone_found, source=source_type, contact_name=c_name, contact_title=c_title)

            results.append({
                'company_key': ck,
                'email': email,
                'domain': domain,
                'phone': phone_found,
                'source': source_type,
                'contact_name': c_name,
                'contact_title': c_title,
                'credits': 1
            })

    print(f"\n2. Enrichment Execution Summary:")
    print(f"   - Total target leads evaluated: {len(results)}")
    print(f"   - Companies not indexed / no decision maker: {not_indexed_count}")
    if not write:
        print(f"   - Matches eligible for reveal: {len(results) - not_indexed_count}")
        print(f"   - Total estimated credit spend: {credits_spent} credits")
        print("\n[DRY RUN COMPLETE] Zero credits spent, zero database modifications.")
    else:
        print(f"   - Direct person phones resolved (apollo_person): {direct_phones_found}")
        print(f"   - Organization phones resolved (apollo_org): {org_phones_found}")
        print(f"   - No phone available (apollo_none recorded): {no_phone_found}")
        print(f"   - Total actual credits spent: {credits_spent} credits")
        print("\n[WRITE COMPLETE] Leads table updated with resolved contact details and audit sources.")

    return results, credits_spent


def main():
    parser = argparse.ArgumentParser(description="ACTION-011 Part C Apollo Enrichment Runner")
    parser.add_argument("--write", action="store_true", default=False, help="Perform real Apollo reveal calls and write to database")
    parser.add_argument("--max-credits", type=int, default=0, help="Maximum Apollo credits allowed to spend (default: 0 = unlimited)")
    parser.add_argument("--mcp-url", type=str, default="http://localhost:5678/mcp/amatec-radar", help="n8n MCP server endpoint")
    args = parser.parse_args()

    run_enrichment(write=args.write, max_credits=args.max_credits, mcp_url=args.mcp_url)


if __name__ == "__main__":
    main()
