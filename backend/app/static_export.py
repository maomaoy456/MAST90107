"""Export the live aggregate API as a portable, read-only dashboard snapshot."""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
import shutil
from urllib.parse import urlencode

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import PROJECT_ROOT, Settings
from app.db import build_engine, session_factory
from app.main import create_app
from app.models import Student


FRONTEND = PROJECT_ROOT / "frontend"
DEFAULT_SITE = PROJECT_ROOT / "static_dashboard"
DEFAULT_DEMO = PROJECT_ROOT / "demo" / "index.html"
ASSETS = ("app.js", "page-visuals.js", "insights-visuals.js", "styles.css")
FORBIDDEN_KEYS = {
    "student_id", "student_number", "identity_digest", "identity_hash", "response_id",
    "canvas_user_id", "account_name", "contact_name", "case_owner", "person_id",
    "dashboard_api_key", "identity_hmac_key", "database_url", "password",
}
EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")


def request_key(path: str, params: dict[str, str] | None = None) -> str:
    query = urlencode(sorted((params or {}).items()))
    return path + ("?" + query if query else "")


def grouped_assignment_refs(options: list[dict]) -> list[str]:
    groups: dict[str, list[str]] = {}
    for item in options:
        if item.get("assessment_key"):
            groups.setdefault(item["assessment_key"], []).append(item["ref"])
    return [",".join(sorted(refs)) for refs in groups.values() if len(refs) > 1]


def collect_snapshot(settings: Settings) -> dict:
    responses: dict[str, object] = {}
    headers = {"X-API-Key": settings.dashboard_api_key.get_secret_value()}

    def get(client: TestClient, path: str, params: dict[str, str] | None = None):
        response = client.get("/api" + path, params=params, headers=headers)
        response.raise_for_status()
        payload = response.json()
        responses[request_key(path, params)] = payload
        return payload

    with TestClient(create_app(settings)) as client:
        get(client, "/v1/health")
        catalog = get(client, "/v1/catalog")
        for course in catalog["courses"]:
            code = course["code"]
            offerings = [item["code"] for item in catalog["offerings"] if item["course"] == code]
            scopes = [None, *offerings]
            for offering in scopes:
                base = {"course": code, **({"offering": offering} if offering else {})}
                for page in ("overview", "data-rules"):
                    get(client, f"/v1/{page}", base)
                get(client, "/v1/rules", base)
                for page in ("engagement", "outcomes"):
                    for interval in ("day", "week", "month"):
                        get(client, f"/v1/{page}", {**base, "interval": interval})
                for mode in ("combined", "scored", "self_assessment"):
                    assignment_params = {**base, "mode": mode}
                    options = get(client, "/v1/assignment-options", assignment_params)
                    get(client, "/v1/assignments", assignment_params)
                    selections = [item["ref"] for item in options]
                    if offering is None:
                        selections += grouped_assignment_refs(options)
                    for selection in dict.fromkeys(selections):
                        get(client, "/v1/assignments", {**assignment_params, "assignments": selection})
            for target in ("all", "AT1", "AT2", "weighted_final", "badge"):
                get(client, "/v1/insights", {"course": code, "target": target})
            get(client, "/v1/models", {"course": code})

    return {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "read_only": True,
            "courses": [item["code"] for item in catalog["courses"]],
            "request_count": len(responses),
        },
        "responses": responses,
    }


def scan_snapshot(snapshot: dict, settings: Settings) -> None:
    problems: list[str] = []

    def walk(value, path="snapshot"):
        if isinstance(value, dict):
            for key, child in value.items():
                if key.lower() in FORBIDDEN_KEYS:
                    problems.append(f"forbidden field at {path}.{key}")
                walk(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]")
        elif isinstance(value, str) and EMAIL.search(value):
            problems.append(f"unredacted email at {path}")

    walk(snapshot)
    encoded = json.dumps(snapshot, ensure_ascii=False)
    secrets = [
        settings.database_url.get_secret_value(),
        settings.dashboard_api_key.get_secret_value() if settings.dashboard_api_key else "",
        settings.identity_hmac_key.get_secret_value() if settings.identity_hmac_key else "",
    ]
    for secret in filter(None, secrets):
        if secret in encoded:
            problems.append("configured secret found in snapshot")
    engine = build_engine(settings)
    try:
        with session_factory(engine)() as session:
            if any(digest in encoded for digest in session.scalars(select(Student.identity_digest))):
                problems.append("student identity digest found in snapshot")
    finally:
        engine.dispose()
    if problems:
        raise ValueError("Static export blocked: " + "; ".join(problems[:10]))


def javascript_assignment(snapshot: dict) -> str:
    payload = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return "window.__MPE_STATIC_SNAPSHOT__=" + payload + ";\n"


def write_site(snapshot: dict, output: Path) -> None:
    output = output.resolve()
    if output.parent != PROJECT_ROOT:
        raise ValueError("Static site output must be a direct child of the project root")
    temporary = PROJECT_ROOT / (output.name + ".tmp")
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir()
    index = (FRONTEND / "index.html").read_text(encoding="utf-8")
    index = re.sub(r'(<script type="module" src="app\.js\?[^\"]+"></script>)',
        r'<script src="snapshot.js"></script>\n  \1', index)
    (temporary / "index.html").write_text(index, encoding="utf-8")
    (temporary / "snapshot.js").write_text(javascript_assignment(snapshot), encoding="utf-8")
    for name in ASSETS:
        shutil.copy2(FRONTEND / name, temporary / name)
    (temporary / "snapshot-manifest.json").write_text(
        json.dumps(snapshot["meta"], indent=2, ensure_ascii=False), encoding="utf-8")
    if output.exists():
        shutil.rmtree(output)
    temporary.replace(output)


def write_offline_html(snapshot: dict, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    css = (FRONTEND / "styles.css").read_text(encoding="utf-8")
    modules = {}
    for name in ("page-visuals.js", "insights-visuals.js"):
        source = (FRONTEND / name).read_bytes()
        modules[name] = "data:text/javascript;base64," + base64.b64encode(source).decode("ascii")
    app = (FRONTEND / "app.js").read_text(encoding="utf-8")
    app = re.sub(r'"\.\/page-visuals\.js\?[^\"]+"', json.dumps(modules["page-visuals.js"]), app)
    app = re.sub(r'"\.\/insights-visuals\.js\?[^\"]+"', json.dumps(modules["insights-visuals.js"]), app)
    html = re.sub(r'<link rel="stylesheet"[^>]+>', lambda _: f"<style>\n{css}\n</style>", html)
    scripts = f"<script>{javascript_assignment(snapshot)}</script>\n  <script type=\"module\">\n{app}\n</script>"
    html = re.sub(r'<script type="module" src="app\.js\?[^\"]+"></script>', lambda _: scripts, html)
    output.write_text(html, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, default=DEFAULT_SITE)
    parser.add_argument("--demo", type=Path, default=DEFAULT_DEMO)
    args = parser.parse_args()
    settings = Settings()
    if settings.dashboard_api_key is None:
        raise SystemExit("DASHBOARD_API_KEY is required")
    logging.disable(logging.CRITICAL)
    try:
        snapshot = collect_snapshot(settings)
    finally:
        logging.disable(logging.NOTSET)
    scan_snapshot(snapshot, settings)
    write_site(snapshot, args.site)
    write_offline_html(snapshot, args.demo)
    print(f"Static export complete: {snapshot['meta']['request_count']} aggregate responses")
    print(f"Site: {args.site.resolve()}")
    print(f"Offline demo: {args.demo.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
