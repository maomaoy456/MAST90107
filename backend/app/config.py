from pathlib import Path

from datetime import date
from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", extra="ignore", hide_input_in_errors=True
    )
    database_url: SecretStr
    raw_data_root: Path = PROJECT_ROOT / "datasets"
    identity_hmac_key: SecretStr | None = None
    dashboard_api_key: SecretStr | None = None
    dashboard_backend_url: str = "http://127.0.0.1:8001"
    badge_data_as_of: date | None = None
    model_artifact_root: Path = PROJECT_ROOT / "model_artifacts"
    app_env: str = "development"

    @field_validator("database_url")
    @classmethod
    def mysql_only(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
            if url.drivername != "mysql+pymysql" or not url.database:
                raise ValueError
        except Exception:
            raise ValueError("DATABASE_URL must use mysql+pymysql and name a database") from None
        return value

    @field_validator("raw_data_root")
    @classmethod
    def absolute_raw_root(cls, value: Path) -> Path:
        return (PROJECT_ROOT / value).resolve() if not value.is_absolute() else value.resolve()

    @field_validator("model_artifact_root")
    @classmethod
    def absolute_model_root(cls, value: Path) -> Path:
        return (PROJECT_ROOT / value).resolve() if not value.is_absolute() else value.resolve()
