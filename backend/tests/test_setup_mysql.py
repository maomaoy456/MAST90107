from app import setup_mysql


def test_setup_preserves_existing_environment(tmp_path, monkeypatch):
    monkeypatch.setattr(setup_mysql, "PROJECT_ROOT", tmp_path)
    path = tmp_path / ".env"
    path.write_text("existing-settings")
    assert setup_mysql.main() == 1
    assert path.read_text() == "existing-settings"


def test_setup_saves_only_project_credentials(tmp_path, monkeypatch, capsys):
    statements = []

    class Connection:
        def cursor(self): return self
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, statement, parameters=None): statements.append(statement)
        def fetchone(self): return ("8.0.40",)
        def close(self): pass

    monkeypatch.setattr(setup_mysql, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr("builtins.input", lambda prompt: "root")
    monkeypatch.setattr(setup_mysql, "getpass", lambda prompt: "ADMIN-SENSITIVE")
    monkeypatch.setattr(setup_mysql.pymysql, "connect", lambda **kwargs: Connection())
    assert setup_mysql.main() == 0
    saved = (tmp_path / ".env").read_text()
    assert "TEST_DATABASE_URL=" in saved and "DATABASE_URL=mysql+pymysql://mpe_" in saved
    assert "ADMIN-SENSITIVE" not in saved + capsys.readouterr().out
    assert not any("DROP " in sql or "ALTER " in sql for sql in statements)


def test_setup_connection_failure_is_private(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(setup_mysql, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr("builtins.input", lambda prompt: "root")
    monkeypatch.setattr(setup_mysql, "getpass", lambda prompt: "ADMIN-SENSITIVE")
    def fail(**kwargs):
        raise RuntimeError("ADMIN-SENSITIVE")
    monkeypatch.setattr(setup_mysql.pymysql, "connect", fail)
    assert setup_mysql.main() == 1
    assert "ADMIN-SENSITIVE" not in capsys.readouterr().out
    assert not (tmp_path / ".env").exists()
