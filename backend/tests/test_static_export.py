from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from app.static_export import request_key, grouped_assignment_refs, scan_snapshot, write_offline_html


def test_request_key_is_stable_and_groups_assignments():
    assert request_key("/v1/page", {"target": "AT1", "course": "ABC"}) == "/v1/page?course=ABC&target=AT1"
    options = [
        {"assessment_key": "AT1", "ref": "b"},
        {"assessment_key": "AT1", "ref": "a"},
        {"assessment_key": "AT2", "ref": "c"},
    ]
    assert grouped_assignment_refs(options) == ["a,b"]


def test_scan_rejects_direct_identifiers(engine, monkeypatch):
    settings = SimpleNamespace(database_url=SecretStr("mysql+pymysql://local:private@localhost/test"),
        dashboard_api_key=SecretStr("dashboard-secret"), identity_hmac_key=SecretStr("identity-secret"))
    monkeypatch.setattr("app.static_export.build_engine", lambda unused: engine)
    with pytest.raises(ValueError, match="forbidden field"):
        scan_snapshot({"student_id": "123"}, settings)


def test_offline_html_embeds_assets(tmp_path, monkeypatch):
    from app import static_export
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "index.html").write_text('<link rel="stylesheet" href="styles.css?v=1"><script type="module" src="app.js?v=1"></script>')
    (frontend / "styles.css").write_text("body{}")
    (frontend / "page-visuals.js").write_text("export function a(){}")
    (frontend / "insights-visuals.js").write_text("export function b(){}")
    (frontend / "app.js").write_text('import {a} from "./page-visuals.js?v=1"; import {b} from "./insights-visuals.js?v=1";')
    monkeypatch.setattr(static_export, "FRONTEND", frontend)
    output = tmp_path / "demo" / "index.html"
    write_offline_html({"meta": {}, "responses": {"/v1/test": {"text": "<safe>"}}}, output)
    rendered = output.read_text()
    assert "window.__MPE_STATIC_SNAPSHOT__" in rendered
    assert "data:text/javascript;base64" in rendered
    assert 'src="app.js' not in rendered and 'href="styles.css' not in rendered
