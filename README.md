# Cold Email Outreach CLI

A Python command-line application that runs a four-stage cold outreach pipeline:

1. Ocean.io finds lookalike companies from a seed domain.
2. Prospeo finds C-suite and VP decision makers for those companies.
3. Eazyreach resolves verified work emails from LinkedIn URLs.
4. Brevo sends personalized cold outreach emails after explicit confirmation.

The pipeline saves intermediate JSON files in `data/` so you can resume after a crash or API issue.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and add your API keys:

```env
OCEAN_API_KEY=...
PROSPEO_API_KEY=...
EAZYREACH_API_KEY=...
BREVO_API_KEY=...
BREVO_SENDER_NAME=Your Name
BREVO_SENDER_EMAIL=you@yourdomain.com
```

Make sure your Brevo sender email/domain is verified before sending.

## Run

```bash
python main.py --seed-domain stripe.com
```

The app will:

- find 10 lookalike companies,
- find up to 3 decision makers per company,
- resolve verified work emails,
- show a summary table,
- ask you to type `YES` before sending.

Use a dry run when testing:

```bash
python main.py --seed-domain stripe.com --dry-run
```

Force all stages to run again and ignore saved files:

```bash
python main.py --seed-domain stripe.com --fresh
```

## Resume Behavior

Stage outputs are saved here:

- `data/stage1_companies.json`
- `data/stage2_contacts.json`
- `data/stage3_emails.json`
- `data/stage4_sent.json`

If a run fails, fix the issue and run the same command again without `--fresh`. Existing stage files will be reused.

## Notes

- The Eazyreach public API documentation was not easily discoverable, so `stage3_eazyreach.py` uses configurable `.env` values for the base URL, endpoint, and auth header.
- If your Ocean.io or Eazyreach account shows a different request shape, update the payload in the relevant stage file.
- The code skips failed contacts and continues, retries 408/429/5xx responses with exponential backoff, and deduplicates contacts by LinkedIn URL and email.

## Email Copy

Subject:

```text
Quick question about [Company Name]
```

Body:

```text
Hi [First Name],

I am a developer and came across [Company Name]. I liked what you are building and had a quick idea around making outbound workflows more automated and measurable.

Would you be open to a short call next week? If it is not relevant, no worries at all.

Best,
Your Name
```
