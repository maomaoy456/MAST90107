"""Register a course before importing its full snapshots; no hardcoded API catalog."""
import argparse
import re
from sqlalchemy import select
from app.config import Settings
from app.db import build_engine, session_factory
from app.models import Course


def register(session, code, name):
    if not re.fullmatch(r"[A-Z0-9]{1,40}", code) or not name.strip() or len(name) > 200:
        raise ValueError("Invalid course metadata")
    existing = session.scalar(select(Course).where(Course.code == code))
    if existing:
        if existing.name != name.strip():
            raise ValueError("Course already exists with a different name")
        return "already_registered"
    session.add(Course(code=code, name=name.strip()))
    session.flush()
    return "registered"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    engine = build_engine(Settings())
    try:
        with session_factory(engine).begin() as session:
            result = register(session, args.code, args.name)
        print(result)
        return 0
    except Exception:
        print("Course registration failed; verify the code, name and database connection.")
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
