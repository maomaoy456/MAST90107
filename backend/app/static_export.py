"""Export live aggregate data as a portable dashboard snapshot with editable notes."""
from __future__ import annotations

import argparse
import base64
import hashlib
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
ASSETS = ("app.js", "page-visuals.js", "insights-visuals.js", "chart-notes.js", "chart-copy.js", "submission-chart.js", "styles.css")
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
            get(client, "/v1/data-rules", {"course": code})
            scopes = [None, *offerings]
            for offering in scopes:
                base = {"course": code, **({"offering": offering} if offering else {})}
                get(client, "/v1/insight-notes", base)
                get(client, "/v1/overview", base)
                get(client, "/v1/rules", base)
                for interval in ("day", "week", "month"):
                    get(client, "/v1/engagement", {**base, "interval": interval})
                get(client, "/v1/outcomes", base)
                for mode in ("combined", "scored", "self_assessment"):
                    assignment_params = {**base, "mode": mode}
                    options = get(client, "/v1/assignment-options", assignment_params)
                    get(client, "/v1/assignments", assignment_params)
                    selections = [item["ref"] for item in options]
                    if offering is None:
                        selections += grouped_assignment_refs(options)
                    for selection in dict.fromkeys(selections):
                        get(client, "/v1/assignments", {**assignment_params, "assignments": selection})
            get(client, "/v1/insights", {"course": code})
            for target in ("pass", "badge"):
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
    snapshot_js = javascript_assignment(snapshot)
    version = hashlib.sha256(snapshot_js.encode("utf-8")).hexdigest()[:12]
    index = re.sub(r'(<script type="module" src="app\.js\?[^\"]+"></script>)',
        lambda match: f'<script src="snapshot.js?v={version}"></script>\n  {match.group(1)}', index)
    (temporary / "index.html").write_text(index, encoding="utf-8")
    (temporary / "snapshot.js").write_text(snapshot_js, encoding="utf-8")
    for name in ASSETS:
        shutil.copy2(FRONTEND / name, temporary / name)
    (temporary / "snapshot-manifest.json").write_text(
        json.dumps(snapshot["meta"], indent=2, ensure_ascii=False), encoding="utf-8")
    (temporary / "offline-shell.html").write_text(offline_shell(), encoding="utf-8")
    if output.exists():
        shutil.rmtree(output)
    temporary.replace(output)


def offline_shell() -> str:
    """Bundle relative JS imports recursively so downloaded notes need no assets."""
    modules = {}
    pattern = re.compile(r'"\./([\w-]+\.js)\?[^\"]+"')

    def bundle(name):
        if name not in modules:
            source = (FRONTEND / name).read_text(encoding="utf-8")
            source = pattern.sub(lambda match: json.dumps(bundle(match.group(1))), source)
            modules[name] = "data:text/javascript;base64," + base64.b64encode(source.encode("utf-8")).decode("ascii")
        return modules[name]

    app = (FRONTEND / "app.js").read_text(encoding="utf-8")
    app = pattern.sub(lambda match: json.dumps(bundle(match.group(1))), app)
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    css = (FRONTEND / "styles.css").read_text(encoding="utf-8")
    html = re.sub(r'<link rel="stylesheet"[^>]+>', lambda _: f"<style>\n{css}\n</style>", html)
    scripts = '<script id="dashboardSnapshot"></script>\n<script type="module">\n' + app + '\n</script>'
    return re.sub(r'<script type="module" src="app\.js\?[^\"]+"></script>', lambda _: scripts, html)


def write_offline_html(snapshot: dict, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    html = offline_shell().replace('<script id="dashboardSnapshot"></script>',
        '<script id="dashboardSnapshot">' + javascript_assignment(snapshot) + '</script>')
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
