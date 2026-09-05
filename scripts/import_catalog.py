import argparse
import hashlib
import json
import sys
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db.session import SessionLocal
from app.domain.models import CatalogProductInput
from app.repositories.catalog import CatalogOwnershipConflict, import_catalog


def main() -> None:
    parser = argparse.ArgumentParser(description="Import merchant-authoritative JANUS catalog JSON.")
    parser.add_argument("catalog", type=Path, help="UTF-8 JSON file containing a product array")
    parser.add_argument("--merchant", required=True, help="Expected merchant_id for every product")
    parser.add_argument("--dry-run", action="store_true", help="Validate without changing the database")
    args = parser.parse_args()

    raw = args.catalog.read_bytes()
    try:
        payload = json.loads(raw)
        records = TypeAdapter(list[CatalogProductInput]).validate_python(payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise SystemExit(f"Catalog rejected: {exc}") from exc
    if not records:
        raise SystemExit("Catalog rejected: at least one product is required")
    mismatches = sorted({item.merchant_id for item in records if item.merchant_id != args.merchant})
    if mismatches:
        raise SystemExit(f"Catalog rejected: merchant ownership mismatch ({', '.join(mismatches)})")

    digest = hashlib.sha256(raw).hexdigest()
    if args.dry_run:
        print(f"Catalog valid: {len(records)} products for {args.merchant}; sha256={digest}")
        return

    try:
        with SessionLocal() as db:
            report = import_catalog(db, records, source=f"json_sha256:{digest}")
    except CatalogOwnershipConflict as exc:
        raise SystemExit(f"Catalog rejected: {exc}") from exc
    print(
        f"Catalog imported for {args.merchant}: "
        f"{report.created} created, {report.updated} updated, "
        f"{report.unchanged} unchanged; sha256={digest}"
    )


if __name__ == "__main__":
    main()
