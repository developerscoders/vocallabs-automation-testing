import argparse
import sys

from common import load_environment
import stage1_ocean
import stage2_prospeo
import stage3_eazyreach
import stage4_brevo


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a four-stage cold email outreach pipeline.")
    parser.add_argument("--seed-domain", help="Seed company domain, for example stripe.com")
    parser.add_argument("--fresh", action="store_true", help="Ignore cached JSON files and rerun every stage.")
    parser.add_argument("--dry-run", action="store_true", help="Run all stages but do not send Brevo emails.")
    parser.add_argument("--company-limit", type=int, default=10, help="Number of Ocean.io lookalike companies.")
    parser.add_argument("--contacts-per-company", type=int, default=3, help="Max Prospeo contacts per company.")
    args = parser.parse_args()

    load_environment()

    seed_domain = args.seed_domain or input("Seed company domain (example: stripe.com): ").strip()
    if not seed_domain:
        print("A seed domain is required.")
        return 1

    resume = not args.fresh
    try:
        domains = stage1_ocean.run(seed_domain, resume=resume, limit=args.company_limit)
        contacts = stage2_prospeo.run(domains, resume=resume, per_company=args.contacts_per_company)
        resolved = stage3_eazyreach.run(contacts, resume=resume)
        stage4_brevo.run(resolved, resume=resume, dry_run=args.dry_run)
    except KeyboardInterrupt:
        print("\nPipeline interrupted. Re-run without --fresh to resume from saved JSON files.")
        return 130
    except Exception as exc:
        print(f"Pipeline stopped: {exc}")
        print("Fix the issue and re-run without --fresh to resume from the latest saved stage.")
        return 1

    print("Pipeline complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
