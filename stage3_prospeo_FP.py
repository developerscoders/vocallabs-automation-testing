# Stage 3: Email resolution via Prospeo Enrich Person API
# Eazyreach is no longer used. Prospeo's /enrich-person endpoint resolves
# verified work emails from the person_id (or linkedin_url) collected in Stage 2.

from typing import Any

from common import DATA_DIR, dedupe_by, load_json, pace_api_calls, request_with_retries, require_env, save_json


OUTPUT_FILE = DATA_DIR / "stage3_emails.json"
PROSPEO_ENRICH_URL = "https://api.prospeo.io/enrich-person"


def run(contacts: list[dict[str, str]], *, resume: bool = True) -> list[dict[str, str]]:
    if resume:
        cached = load_json(OUTPUT_FILE)
        if cached:
            print(f"Stage 3: loaded {len(cached)} resolved emails from {OUTPUT_FILE}")
            return cached

    print(f"Stage 3: resolving verified work emails via Prospeo for {len(contacts)} contacts...")
    api_key = require_env("PROSPEO_API_KEY")
    resolved: list[dict[str, str]] = []

    for contact in contacts:
        name = contact.get("name", "Unknown")
        print(f"Stage 3: enriching {name}...")
        try:
            data = request_with_retries(
                "POST",
                PROSPEO_ENRICH_URL,
                headers={"X-KEY": api_key, "Content-Type": "application/json"},
                json_payload=_build_payload(contact),
            )
        except Exception as exc:
            print(f"Stage 3: skipping {name}; Prospeo enrich error: {exc}")
            pace_api_calls()
            continue

        if data.get("error"):
            error_code = data.get("error_code", "UNKNOWN")
            print(f"Stage 3: no match for {name} ({error_code})")
            pace_api_calls()
            continue

        email = _extract_email(data)
        if not email:
            print(f"Stage 3: no verified email found for {name}")
            pace_api_calls()
            continue

        linkedin_url = _extract_linkedin(data) or contact.get("linkedin_url", "")
        resolved.append(
            {
                "name": contact["name"],
                "email": email,
                "company_domain": contact["company_domain"],
                "linkedin_url": linkedin_url,
                "title": contact.get("title", ""),
            }
        )
        print(f"Stage 3: resolved {name} → {email}")
        pace_api_calls()

    resolved = dedupe_by(resolved, lambda item: item.get("email", ""))
    save_json(OUTPUT_FILE, resolved)
    print(f"Stage 3: saved {len(resolved)} unique verified emails to {OUTPUT_FILE}")
    return resolved


def _build_payload(contact: dict[str, str]) -> dict[str, Any]:
    """
    Build the enrich-person payload.
    Priority: person_id (most accurate, free re-enrichment) → linkedin_url → name+domain.
    """
    person_id = contact.get("person_id", "").strip()
    linkedin_url = contact.get("linkedin_url", "").strip()
    company_domain = contact.get("company_domain", "").strip()
    full_name = contact.get("name", "").strip()

    payload: dict[str, Any] = {"only_verified_email": True}

    if person_id:
        payload["data"] = {"person_id": person_id}
    elif linkedin_url:
        payload["data"] = {"linkedin_url": linkedin_url}
    elif full_name and company_domain:
        payload["data"] = {"full_name": full_name, "company_website": company_domain}
    else:
        # Not enough data — caller should skip this contact
        raise ValueError(f"Not enough data to enrich: {contact}")

    return payload


def _extract_email(data: dict[str, Any]) -> str | None:
    person = data.get("person") or {}
    email_obj = person.get("email") or {}
    if not isinstance(email_obj, dict):
        return None
    status = str(email_obj.get("status", "")).upper()
    revealed = email_obj.get("revealed", False)
    email = email_obj.get("email", "")
    if status == "VERIFIED" and revealed and email and "*" not in email:
        return str(email)
    return None


def _extract_linkedin(data: dict[str, Any]) -> str | None:
    person = data.get("person") or {}
    return person.get("linkedin_url") or None