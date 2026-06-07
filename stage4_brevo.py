import os

from common import DATA_DIR, domain_to_company_name, first_name, load_json, pace_api_calls, request_with_retries, require_env, save_json


OUTPUT_FILE = DATA_DIR / "stage4_sent.json"
BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"


def run(contacts: list[dict[str, str]], *, resume: bool = True, dry_run: bool = False) -> list[dict[str, str]]:
    sent = load_json(OUTPUT_FILE, default=[]) if resume else []
    sent_emails = {item.get("email", "").lower() for item in sent}
    pending = [contact for contact in contacts if contact.get("email", "").lower() not in sent_emails]

    if not pending:
        print("Stage 4: no new contacts to email.")
        return sent

    print("Stage 4: contacts queued for outreach:")
    _print_summary_table(pending)
    confirmation = input("Send these emails? Type YES to confirm: ").strip()
    if confirmation != "YES":
        print("Stage 4: cancelled before sending.")
        return sent

    if dry_run:
        print("Stage 4: dry run enabled; no emails sent.")
        return sent

    api_key = require_env("BREVO_API_KEY")
    sender_name = require_env("BREVO_SENDER_NAME")
    sender_email = require_env("BREVO_SENDER_EMAIL")
    reply_to_email = os.getenv("BREVO_REPLY_TO_EMAIL")
    sent_now: list[dict[str, str]] = []

    for contact in pending:
        company_name = domain_to_company_name(contact["company_domain"])
        subject = f"Quick question about {company_name}"
        body = build_email_body(contact["name"], company_name, sender_name)
        payload = _build_brevo_payload(sender_name, sender_email, contact, subject, body, reply_to_email)
        print(f"Stage 4: sending to {contact['name']} <{contact['email']}>...")
        try:
            response = request_with_retries(
                "POST",
                BREVO_SEND_URL,
                headers={"api-key": api_key, "Content-Type": "application/json", "Accept": "application/json"},
                json_payload=payload,
            )
        except Exception as exc:
            print(f"Stage 4: failed to send to {contact['email']}; skipping. Error: {exc}")
            pace_api_calls()
            continue

        record = {
            **contact,
            "subject": subject,
            "message_id": str(response.get("messageId") or response.get("message_id") or ""),
        }
        sent_now.append(record)
        sent.append(record)
        save_json(OUTPUT_FILE, sent)
        pace_api_calls()

    print(f"Stage 4: sent {len(sent_now)} emails. Total sent records in {OUTPUT_FILE}: {len(sent)}")
    return sent


def build_email_body(full_name: str, company_name: str, sender_name: str = "") -> str:
    name = first_name(full_name)
    sign_off = sender_name.strip() or os.getenv("BREVO_SENDER_NAME", "Your Name")
    return (
        f"Hi {name},\n\n"
        f"I am a developer and came across {company_name}. I liked what you are building and had a quick idea "
        "around making outbound workflows more automated and measurable.\n\n"
        "Would you be open to a short call next week? If it is not relevant, no worries at all.\n\n"
        f"Best,\n{sign_off}"
    )


def _build_brevo_payload(
    sender_name: str,
    sender_email: str,
    contact: dict[str, str],
    subject: str,
    body: str,
    reply_to_email: str | None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "sender": {"name": sender_name, "email": sender_email},
        "to": [{"email": contact["email"], "name": contact["name"]}],
        "subject": subject,
        "htmlContent": _plain_text_to_html(body),
        "textContent": body,
    }
    if reply_to_email:
        payload["replyTo"] = {"email": reply_to_email, "name": sender_name}
    return payload


def _print_summary_table(contacts: list[dict[str, str]]) -> None:
    rows = [["Name", "Email", "Company"]]
    rows.extend([[item["name"], item["email"], item["company_domain"]] for item in contacts])
    widths = [max(len(str(row[index])) for row in rows) for index in range(3)]
    for index, row in enumerate(rows):
        print(" | ".join(str(value).ljust(widths[i]) for i, value in enumerate(row)))
        if index == 0:
            print("-+-".join("-" * width for width in widths))


def _plain_text_to_html(text: str) -> str:
    escaped = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>")
    )
    return f"<html><body><p>{escaped}</p></body></html>"