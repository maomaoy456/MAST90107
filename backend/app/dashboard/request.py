"""Call the running local server without putting its API key in shell history."""
import argparse
import json

import httpx
from app.config import Settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("page", choices=["catalog", "assignment-options", "overview", "engagement", "assignments", "outcomes", "insights", "models", "data-rules", "rules"])
    parser.add_argument("--course")
    parser.add_argument("--target", choices=["all", "AT1", "AT2", "weighted_final", "badge"])
    parser.add_argument("--offering")
    parser.add_argument("--offerings")
    parser.add_argument("--assignments")
    parser.add_argument("--interval", choices=["day", "week", "month"])
    parser.add_argument("--mode", choices=["combined", "scored", "self_assessment"])
    args = parser.parse_args()
    settings = Settings()
    if settings.dashboard_api_key is None:
        print("DASHBOARD_API_KEY is not configured.")
        return 1
    params = {name: getattr(args, name) for name in ("course", "offering", "offerings", "assignments", "interval", "mode", "target") if getattr(args, name) is not None}
    try:
        response = httpx.get(settings.dashboard_backend_url.rstrip("/") + "/api/v1/" + args.page, params=params,
            headers={"X-API-Key": settings.dashboard_api_key.get_secret_value()}, timeout=30)
        print("HTTP", response.status_code)
        print(json.dumps(response.json(), ensure_ascii=False, indent=2))
        return 0 if response.is_success else 1
    except Exception:
        print("Local request failed; check that the API server is running.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
