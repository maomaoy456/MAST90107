"""Train reviewed targets locally; prints aggregate status only."""
import argparse
from app.config import Settings
from app.db import build_engine, session_factory
from app.modeling.training import train


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--course", required=True)
    parser.add_argument("--target", choices=["AT1", "AT2", "weighted_final", "badge", "all"], default="all")
    args = parser.parse_args()
    settings = Settings()
    engine = build_engine(settings)
    try:
        targets = ("AT1", "AT2", "weighted_final", "badge") if args.target == "all" else (args.target,)
        with session_factory(engine)() as session:
            for target in targets:
                try:
                    run, current = train(session, settings, args.course, target)
                    score = (run.metrics or {}).get(run.model_name, {}).get("macro_f1")
                    suffix = " / already current" if current else ""
                    print(f"{args.course} / {target}: {run.status} / {run.model_name} / macro_f1={score}{suffix}")
                except ValueError:
                    print(f"{args.course} / {target}: rejected configuration")
                    return 1
                except Exception:
                    print(f"{args.course} / {target}: training failed; private details withheld")
                    return 1
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
