"""Run: python -m app.ingestion init-key | import-all | import-file | report."""
import argparse
import json
from pathlib import Path
import secrets

from sqlalchemy import func, select

from app.config import PROJECT_ROOT, Settings
from app.db import build_engine, session_factory
from app.ingestion.report import build_report
from app.ingestion.service import import_file
from app.logging import configure_logging
from app.models import Student
from app.preflight import FILES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["init-key", "import-all", "import-file", "report", "verify"])
    parser.add_argument("--source", choices=list(FILES))
    parser.add_argument("--file", type=Path)
    args = parser.parse_args()
    configure_logging()
    engine = None
    try:
        settings = Settings()
        engine = build_engine(settings)
        factory = session_factory(engine)
        if args.action == "init-key":
            if settings.identity_hmac_key:
                print("Identity key already configured; preserved.")
                return 0
            with factory() as session:
                if session.scalar(select(func.count()).select_from(Student)):
                    raise ValueError("Existing identities require their original key")
            with (PROJECT_ROOT / ".env").open("a", encoding="utf-8") as output:
                output.write("\nIDENTITY_HMAC_KEY=" + secrets.token_urlsafe(48) + "\n")
            print("Identity key saved locally. Keep .env private and backed up; never rotate it silently.")
            return 0
        if args.action != "report":
            key = settings.identity_hmac_key.get_secret_value() if settings.identity_hmac_key else ""
            if len(key) < 32:
                print("Configure the identity key first: python -m app.ingestion init-key")
                return 1
            if args.action == "verify":
                from app.ingestion.verify import verify_file
                results = {source: verify_file(factory, settings.raw_data_root / name, source, key)
                           for source, name in FILES.items()}
                print(json.dumps(results))
                return 0 if all(results.values()) else 1
            if args.action == "import-file":
                if not args.source or not args.file:
                    parser.error("import-file requires --source and --file")
                inputs = [(args.source, args.file)]
            else:
                inputs = [(s, settings.raw_data_root / FILES[s]) for s in ("assignment", "engagement", "badge")]
            for source, path in inputs:
                result = import_file(factory, path, source, key)
                print(source + ": " + result)
        with factory() as session:
            report = build_report(session)
        print(json.dumps(report, indent=2))
        return 0
    except Exception:
        print("Operation failed. Check migration, source contract and import_errors codes; raw values were not printed.")
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
