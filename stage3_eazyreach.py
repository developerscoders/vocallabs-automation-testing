import os
from typing import Any

from common import DATA_DIR, dedupe_by, load_json, request_with_retries, require_env, save_json


OUTPUT_FILE = DATA_DIR / "stage3_emails.json"


def run(contacts: list[dict[str, str]], *, resume: bool = True) -> list[dict[str, str]]:
    if resume:
        cached = load_json(OUTPUT_FILE)
        if cached:
            print(f"Stage 3: loaded {len(cached)} resolved emails from {OUTPUT_FILE}")
            return cached

    print(f"Stage 3: resolving verified work emails with Eazyreach for {len(contacts)} contacts...")
    api_key = require_env("EAZYREACH_API_KEY")
    base_url = os.getenv("EAZYREACH_BASE_URL", "https://api.eazyreach.app").rstrip("/")
    endpoint = os.getenv("EAZYREACH_EMAIL_ENDPOINT", "/api/v1/email-finder")
    url = f"{base_url}{endpoint if endpoint.startswith('/') else '/' + endpoint}"
    header_name = os.getenv("EAZYREACH_AUTH_HEADER", "Authorization")
    header_value = f"Bearer {api_key}" if header_name.lower() == "authorization" else api_key

    resolved: list[dict[str, str]] = []
    for contact in contacts:
        linkedin_url = contact.get("linkedin_url", "")
        print(f"Stage 3: resolving {contact.get('name', 'Unknown')}...")
        try:
            data = request_with_retries(
                "POST",
                url,
                headers={header_name: header_value, "Content-Type": "application/json"},
                json_payload={"linkedin_url": linkedin_url},
            )
        except Exception as exc:
            print(f"Stage 3: skipping {linkedin_url}; Eazyreach error: {exc}")
            continue

        email = _extract_email(data)
        if not email:
            print(f"Stage 3: no verified email for {contact.get('name', linkedin_url)}")
            continue

        resolved.append(
            {
                "name": contact["name"],
                "email": email,
                "company_domain": contact["company_domain"],
                "linkedin_url": linkedin_url,
            }
        )

    resolved = dedupe_by(resolved, lambda item: item.get("email", ""))
    save_json(OUTPUT_FILE, resolved)
    print(f"Stage 3: saved {len(resolved)} unique verified emails to {OUTPUT_FILE}")
    return resolved


def _extract_email(data: dict[str, Any]) -> str | None:
    possible = [
        data.get("email"),
        data.get("work_email"),
        data.get("verified_email"),
        data.get("data", {}).get("email") if isinstance(data.get("data"), dict) else None,
        data.get("result", {}).get("email") if isinstance(data.get("result"), dict) else None,
        data.get("contact", {}).get("email") if isinstance(data.get("contact"), dict) else None,
    ]
    status = str(
        data.get("status")
        or (data.get("data", {}).get("status") if isinstance(data.get("data"), dict) else "")
        or ""
    ).lower()
    for email in possible:
        if not email:
            continue
        if status and status not in {"verified", "valid", "success", "found"}:
            return None
        return str(email)
    return None
