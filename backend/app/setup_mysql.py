"""Run interactively on the user's machine; never put the admin password in arguments."""
from getpass import getpass
import secrets

import pymysql
from sqlalchemy.engine import URL

from app.config import PROJECT_ROOT


def main() -> int:
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        print("Existing .env preserved. Use the existing configuration or review it locally.")
        return 1
    username = input("MySQL administrator username [root]: ").strip() or "root"
    password = getpass("MySQL password (hidden; not saved): ")
    connection = None
    try:
        connection = pymysql.connect(host="127.0.0.1", port=3306, user=username,
                                     password=password, connect_timeout=5, autocommit=True)
        # Random names avoid modifying databases/accounts belonging to other projects.
        suffix = secrets.token_hex(4)
        database = "mpe_" + suffix
        test_database = database + "_test"
        app_user = "mpe_" + suffix
        app_password = secrets.token_urlsafe(32)
        dashboard_key = secrets.token_urlsafe(32)
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()[0]
            parts = version.split("-")[0].split(".")
            if "mariadb" in version.lower() or tuple(int(p) for p in parts[:3]) < (8, 0, 16):
                raise ValueError("Unsupported database version")
            cursor.execute(f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin")
            cursor.execute(f"CREATE DATABASE `{test_database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin")
            cursor.execute("CREATE USER %s@'localhost' IDENTIFIED BY %s", (app_user, app_password))
            for name in (database, test_database):
                cursor.execute(f"GRANT ALL PRIVILEGES ON `{name}`.* TO %s@'localhost'", (app_user,))
        def url(name):
            return URL.create("mysql+pymysql", username=app_user, password=app_password,
                              host="127.0.0.1", port=3306, database=name,
                              query={"charset": "utf8mb4"}).render_as_string(hide_password=False)
        # Exclusive creation prevents overwriting a configuration created concurrently.
        with env_path.open("x", encoding="utf-8") as output:
            output.write(f"DATABASE_URL={url(database)}\nTEST_DATABASE_URL={url(test_database)}\nRAW_DATA_ROOT=./datasets\n"
                         f"DASHBOARD_API_KEY={dashboard_key}\nDASHBOARD_BACKEND_URL=http://127.0.0.1:8001\nAPP_ENV=development\n")
        print("Created isolated project/test databases and a project-scoped account. Saved local .env.")
        return 0
    except Exception:
        print("Setup failed; credentials and server errors were not printed. No existing database was changed.")
        print("MySQL DDL is not transactional: newly created empty resources may remain if setup partly succeeded.")
        return 1
    finally:
        password = None
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
