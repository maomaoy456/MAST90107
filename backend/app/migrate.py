"""Privacy-safe Alembic entry point for local and container operations."""
import argparse
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.logging import configure_logging


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["upgrade", "current", "check", "sql"])
    args = parser.parse_args()
    configure_logging()
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    try:
        if args.action == "upgrade":
            command.upgrade(config, "head")
        elif args.action == "current":
            command.current(config)
        elif args.action == "check":
            command.check(config)
        else:
            command.upgrade(config, "head", sql=True)
        return 0
    except Exception:
        print("Migration failed. Check database readiness and migration configuration.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
