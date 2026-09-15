"""Import the reviewed manifest. Each file/scope is one transaction."""
import json
from pathlib import Path
from sqlalchemy import select, text
from app.config import Settings
from app.db import build_engine, session_factory
from app.models import ImportBatch
from app.supplemental.importer import import_calendars, import_survey, import_support


def main():
    settings = Settings()
    if settings.identity_hmac_key is None:
        print("Configure the existing project identity key first.")
        return 1
    key = settings.identity_hmac_key.get_secret_value()
    config = json.loads((Path(__file__).resolve().parents[2] / "config" / "supplemental_sources.json").read_text(encoding="utf-8"))
    engine = build_engine(settings)
    try:
        # Same cooperative lock as the existing importer; connection survives commits.
        with engine.connect() as connection:
            if connection.scalar(text("SELECT GET_LOCK('mpe_file_import', 0)")) != 1:
                raise ValueError("import_in_progress")
            connection.commit()
            factory = session_factory(connection)
            try:
                import hashlib
                with factory() as session:
                    expected = hashlib.sha256(key.encode()).hexdigest()
                    if any(b.summary and b.summary.get("identity_key_fingerprint", expected) != expected for b in session.scalars(select(ImportBatch))):
                        raise ValueError("identity_key_changed")
                with factory.begin() as session:
                    result = import_calendars(session, [settings.raw_data_root / p for p in config["calendars"]], key)
                print("calendar: " + result, flush=True)
                for kind, fn, scope in (("surveys", import_survey, "offering"), ("support", import_support, "course")):
                    for source in config[kind]:
                        with factory.begin() as session:
                            result = fn(session, settings.raw_data_root / source["file"], source[scope], key)
                        print(kind + " / " + source[scope] + ": " + result, flush=True)
            finally:
                connection.execute(text("SELECT RELEASE_LOCK('mpe_file_import')"))
                connection.commit()
        return 0
    except Exception:
        print("Supplemental import failed; incomplete scope rolled back. Check source columns, dates and mappings; private values withheld.")
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
