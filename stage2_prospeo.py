from typing import Any

from common import DATA_DIR, dedupe_by, load_json, pace_api_calls, request_with_retries, require_env, save_json


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
TARGET_SENIORITIES = ["C-Suite", "Vice President", "Founder/Owner"]
MAX_PAGES_PER_COMPANY = 6


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
        contacts = _search_domain_contacts(api_key, domain, per_company)
        print(f"Stage 2: found {len(contacts)} contacts for {domain}")
        all_contacts.extend(contacts)
        pace_api_calls()

    all_contacts = dedupe_by(all_contacts, lambda item: item.get("person_id") or item.get("linkedin_url", ""))
    save_json(OUTPUT_FILE, all_contacts)
    print(f"Stage 2: saved {len(all_contacts)} unique contacts to {OUTPUT_FILE}")
    return all_contacts


def _search_domain_contacts(api_key: str, domain: str, per_company: int) -> list[dict[str, str]]:
    print(f"Stage 2: searching {domain}...")
    contacts: list[dict[str, str]] = []
    page = 1

    while len(contacts) < per_company and page <= MAX_PAGES_PER_COMPANY:
        payload = _build_payload(domain, page)
        try:
            data = request_with_retries(
                "POST",
                PROSPEO_SEARCH_URL,
                headers={"X-KEY": api_key, "Content-Type": "application/json"},
                json_payload=payload,
            )
        except Exception as exc:
            print(f"Stage 2: skipping remaining Prospeo pages for {domain}; error: {exc}")
            break

        page_contacts = _extract_contacts(data, domain)
        if not page_contacts:
            break

        contacts.extend(page_contacts)
        contacts = dedupe_by(contacts, lambda item: item.get("person_id") or item.get("linkedin_url", ""))
        if len(contacts) >= per_company or not _has_more_pages(data, page):
            break

        page += 1
        print(f"Stage 2: fetching page {page} for {domain}...")
        pace_api_calls()

    return contacts[:per_company]


def _build_payload(domain: str, page: int) -> dict[str, Any]:
    return {
        "page": page,
        "filters": {
            "company": {"websites": {"include": [domain]}},
            "person_job_title": {"include": TARGET_TITLES, "match_mode": "CONTAINS"},
            "person_seniority": {"include": TARGET_SENIORITIES},
        },
    }


def _extract_contacts(data: dict[str, Any], fallback_domain: str) -> list[dict[str, str]]:
    contacts: list[dict[str, str]] = []
    for item in _extract_result_items(data):
        person = item.get("person", item) if isinstance(item, dict) else {}
        company = item.get("company", {}) if isinstance(item, dict) else {}

        full_name = person.get("full_name") or person.get("name")
        linkedin_url = person.get("linkedin_url") or person.get("linkedin") or person.get("linkedinUrl")
        person_id = str(person.get("person_id") or "")

        # Need at least name + (person_id or linkedin_url) to enrich later
        if not full_name or (not person_id and not linkedin_url):
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
                "person_id": person_id,
                "linkedin_url": str(linkedin_url or ""),
                "company_domain": _clean_domain(str(company_domain)),
                "title": str(person.get("current_job_title") or person.get("job_title") or ""),
            }
        )
    return contacts


def _extract_result_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("results", "data", "items"):
        value = data.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = value.get("results") or value.get("items") or value.get("data")
            if isinstance(nested, list):
                return nested
    return []


def _has_more_pages(data: dict[str, Any], current_page: int) -> bool:
    if data.get("has_more") is not None:
        return bool(data["has_more"])
    if data.get("hasMore") is not None:
        return bool(data["hasMore"])

    pagination = data.get("pagination") or data.get("meta") or {}
    if isinstance(pagination, dict):
        total_pages = pagination.get("total_pages") or pagination.get("totalPages") or pagination.get("pages")
        if total_pages is not None:
            return current_page < int(total_pages)
        next_page = pagination.get("next_page") or pagination.get("nextPage")
        if next_page is not None:
            return bool(next_page)

    return len(_extract_result_items(data)) > 0


def _clean_domain(domain: str) -> str:
    return domain.replace("https://", "").replace("http://", "").split("/")[0].lower()