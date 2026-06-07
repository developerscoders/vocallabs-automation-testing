from typing import Any

import requests

from common import DATA_DIR, ApiError, dedupe_by, load_json, require_env, save_json


OUTPUT_FILE = DATA_DIR / "stage1_companies.json"
OCEAN_SEARCH_URL = "https://api.ocean.io/v3/search/companies"


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
        "companiesFilters": {
            "lookalikeDomains": [seed_domain],
        },
        "fields": ["domain", "name"],
    }

    data = _ocean_request(api_key, payload, seed_domain)

    companies = _extract_companies(data)
    companies = dedupe_by(companies, lambda item: item.get("domain", ""))[:limit]

    if not companies:
        raise RuntimeError(
            f"Ocean.io returned no lookalike companies for '{seed_domain}'. "
            "This usually means the domain is not in Ocean.io's database. "
            "Try a well-known domain like 'stripe.com' or 'razorpay.com' to verify your API key works, "
            "then try a different seed domain."
        )

    save_json(OUTPUT_FILE, companies)
    print(f"Stage 1: saved {len(companies)} company domains to {OUTPUT_FILE}")
    return [company["domain"] for company in companies]


def _ocean_request(api_key: str, payload: dict[str, Any], seed_domain: str) -> dict[str, Any]:
    """Make the Ocean.io request with clean error handling for non-JSON responses."""
    try:
        response = requests.post(
            OCEAN_SEARCH_URL,
            headers={"x-api-token": api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=45,
        )
    except requests.RequestException as exc:
        raise ApiError(f"Ocean.io request failed: {exc}") from exc

    # Handle rate limits
    if response.status_code == 429:
        raise ApiError(
            f"Ocean.io rate limit hit. Wait a minute then re-run without --fresh."
        )

    # Handle auth errors
    if response.status_code == 401:
        raise ApiError("Ocean.io API key is invalid. Check OCEAN_API_KEY in your .env file.")

    # Empty body = no results
    if not response.text.strip():
        return {}

    # Non-JSON body (e.g. HTML error page) — surface clearly instead of crashing
    try:
        data = response.json()
    except ValueError:
        raise ApiError(
            f"Ocean.io returned a non-JSON response (HTTP {response.status_code}) "
            f"for domain '{seed_domain}'. "
            f"Response preview: {response.text[:300]}"
        )

    if not response.ok:
        detail = data if isinstance(data, dict) else {}
        raise ApiError(
            f"Ocean.io error {response.status_code} for '{seed_domain}': {detail}"
        )

    return data


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