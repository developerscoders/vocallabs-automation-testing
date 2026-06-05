from typing import Any

from common import DATA_DIR, dedupe_by, load_json, request_with_retries, require_env, save_json


OUTPUT_FILE = DATA_DIR / "stage2_contacts.json"
PROSPEO_SEARCH_URL = "https://api.prospeo.io/search-person"
TARGET_TITLES = [
    "CEO",
    "Founder",
    "Co-Founder",
    "President",
    "COO",
    "CRO",
    "CMO",
    "CTO",
    "CIO",
    "VP Sales",
    "VP Marketing",
    "VP Engineering",
    "VP Product",
]


def run(domains: list[str], *, resume: bool = True, per_company: int = 3) -> list[dict[str, str]]:
    if resume:
        cached = load_json(OUTPUT_FILE)
        if cached:
            print(f"Stage 2: loaded {len(cached)} contacts from {OUTPUT_FILE}")
            return cached

    print(f"Stage 2: searching Prospeo for C-suite and VP contacts at {len(domains)} companies...")
    api_key = require_env("PROSPEO_API_KEY")
    all_contacts: list[dict[str, str]] = []

    for domain in domains:
        print(f"Stage 2: searching {domain}...")
        payload = {
            "page": 1,
            "filters": {
                "company": {"websites": {"include": [domain]}},
                "person_job_title": {"include": TARGET_TITLES, "match_mode": "CONTAINS"},
                "person_seniority": {"include": ["C-Suite", "Vice President", "Founder/Owner"]},
            },
        }
        try:
            data = request_with_retries(
                "POST",
                PROSPEO_SEARCH_URL,
                headers={"X-KEY": api_key, "Content-Type": "application/json"},
                json_payload=payload,
            )
        except Exception as exc:
            print(f"Stage 2: skipping {domain}; Prospeo error: {exc}")
            continue

        contacts = _extract_contacts(data, domain)[:per_company]
        print(f"Stage 2: found {len(contacts)} contacts for {domain}")
        all_contacts.extend(contacts)

    all_contacts = dedupe_by(all_contacts, lambda item: item.get("linkedin_url", ""))
    save_json(OUTPUT_FILE, all_contacts)
    print(f"Stage 2: saved {len(all_contacts)} unique contacts to {OUTPUT_FILE}")
    return all_contacts


def _extract_contacts(data: dict[str, Any], fallback_domain: str) -> list[dict[str, str]]:
    contacts: list[dict[str, str]] = []
    for item in data.get("results", []):
        person = item.get("person", item)
        company = item.get("company", {})
        linkedin_url = person.get("linkedin_url")
        full_name = person.get("full_name")
        if not linkedin_url or not full_name:
            continue
        company_domain = (
            company.get("website")
            or company.get("domain")
            or company.get("website_domain")
            or fallback_domain
        )
        contacts.append(
            {
                "name": str(full_name),
                "linkedin_url": str(linkedin_url),
                "company_domain": str(company_domain).replace("https://", "").replace("http://", "").split("/")[0],
                "title": str(person.get("current_job_title") or ""),
            }
        )
    return contacts
