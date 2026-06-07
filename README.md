# Cold Email Outreach CLI

A Python command-line application that runs a four-stage cold outreach pipeline for the Vocallabs SDE assignment:

1. Ocean.io finds lookalike companies from a seed domain.
2. Prospeo finds C-suite and VP decision makers for those companies.
3. Eazyreach resolves verified work emails from LinkedIn URLs.
4. Brevo sends personalized cold outreach emails after explicit confirmation.

The pipeline saves intermediate JSON files in `data/` beside the project files, so it can resume after a crash or API issue no matter which folder you launch it from.

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
BREVO_REPLY_TO_EMAIL=you@yourdomain.com
API_DELAY_SECONDS=1.0
```

Make sure your Brevo sender email/domain is verified before sending.

## Run

```bash
python main.py --seed-domain stripe.com
```

The app will find 10 lookalike companies, find up to 3 decision makers per company, resolve verified work emails, show a summary table, and ask you to type `YES` before any Brevo emails are sent.

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

If a run fails, fix the issue and run the same command again without `--fresh`. Existing stage files will be reused automatically, so there are no manual handoffs between stages.

## PDF Compliance Checklist

- Single command-line program: `main.py` runs all four stages end to end from one seed domain.
- One clear unit per stage: Ocean.io, Prospeo, Eazyreach, and Brevo live in separate stage files.
- Automatic stage chaining: each stage returns structured data used directly by the next stage.
- Pagination: Prospeo search requests continue page by page until enough decision makers are collected or results stop.
- Error handling: failed domains, unresolved contacts, rate limits, and send failures are logged and skipped without crashing the whole run.
- Rate limits: retry logic handles 408, 429, and 5xx responses with exponential backoff; `API_DELAY_SECONDS` paces per-domain/contact calls.
- Deduplication: contacts are deduped by LinkedIn URL before email lookup and by email before sending.
- Safety checkpoint: Stage 4 prints the exact contacts queued for outreach and requires `YES` before sending.

## Eazyreach Configuration

Eazyreach public pages mention API access and LinkedIn contact enrichment, but the public endpoint shape is not stable in open docs. Match these `.env` values to the endpoint shown in your Eazyreach or Vocallabs-provided API docs:

```env
EAZYREACH_BASE_URL=https://api.eazyreach.app
EAZYREACH_EMAIL_ENDPOINT=/api/v1/email-finder
EAZYREACH_AUTH_HEADER=Authorization
EAZYREACH_LINKEDIN_FIELD=linkedin_url
```

If Eazyreach expects a different payload key, update `EAZYREACH_LINKEDIN_FIELD`, for example `profile_url` or `linkedinUrl`.

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

## Test

```bash
python -m unittest discover -s tests
```
