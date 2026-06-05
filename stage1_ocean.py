from typing import Any

from common import DATA_DIR, dedupe_by, load_json, request_with_retries, require_env, save_json


OUTPUT_FILE = DATA_DIR / "stage1_companies.json"
OCEAN_SEARCH_URL = "https://api.ocean.io/v3/search/companies/preview"


def run(seed_domain: str, *, resume: bool = True, limit: int = 10) -> list[str]:
    if resume:
        cached = load_json(OUTPUT_FILE)
        if cached:
            print(f"Stage 1: loaded {len(cached)} company domains from {OUTPUT_FILE}")
            return [item["domain"] if isinstance(item, dict) else item for item in cached][:limit]

    print(f"Stage 1: finding {limit} Ocean.io lookalike companies for {seed_domain}...")
    api_key = require_env("OCEAN_API_KEY")
    payload = {
        "size": limit,
        "filters": {
            "lookalike": {
                "domain": seed_domain,
            }
        },
    }
    data = request_with_retries(
        "POST",
        OCEAN_SEARCH_URL,
        headers={"X-Api-Token": api_key, "Content-Type": "application/json"},
        json_payload=payload,
    )

    companies = _extract_companies(data)
    if not companies:
        # Some Ocean.io accounts expose lookalikes through the non-preview endpoint.
        fallback_url = "https://api.ocean.io/v3/search/companies"
        print("Stage 1: preview response had no domains; trying full search endpoint...")
        data = request_with_retries(
            "POST",
            fallback_url,
            headers={"X-Api-Token": api_key, "Content-Type": "application/json"},
            json_payload=payload,
        )
        companies = _extract_companies(data)

    companies = dedupe_by(companies, lambda item: item.get("domain", ""))[:limit]
    save_json(OUTPUT_FILE, companies)
    print(f"Stage 1: saved {len(companies)} company domains to {OUTPUT_FILE}")
    return [company["domain"] for company in companies]


def _extract_companies(data: dict[str, Any]) -> list[dict[str, str]]:
    candidates = (
        data.get("companies")
        or data.get("results")
        or data.get("data")
        or data.get("items")
        or []
    )
    companies: list[dict[str, str]] = []
    for item in candidates:
        company = item.get("company", item) if isinstance(item, dict) else {}
        domain = (
            company.get("domain")
            or company.get("website")
            or company.get("website_domain")
            or company.get("primary_domain")
        )
        if not domain:
            continue
        clean_domain = str(domain).replace("https://", "").replace("http://", "").split("/")[0].lower()
        companies.append(
            {
                "domain": clean_domain,
                "name": str(company.get("name") or clean_domain),
            }
        )
    return companies
