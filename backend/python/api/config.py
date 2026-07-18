from dataclasses import dataclass
import os

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class SqlConfig:
    driver: str
    server: str
    database: str
    trusted: bool
    user: str | None = None
    password: str | None = None
    trust_server_certificate: bool = True


@dataclass(frozen=True)
class ApiConfig:
    title: str
    version: str
    cors_origins: list[str]
    sql: SqlConfig


def _env_bool(name: str, default: str = "yes") -> bool:
    return os.getenv(name, default).lower() in ("1", "true", "yes", "tak")


def get_config() -> ApiConfig:
    cors = os.getenv("SMARTSUPPLY_API_CORS_ORIGINS", "*")
    return ApiConfig(
        title=os.getenv("SMARTSUPPLY_API_TITLE", "SmartSupply API"),
        version=os.getenv("SMARTSUPPLY_API_VERSION", "0.1.0"),
        cors_origins=[origin.strip() for origin in cors.split(",") if origin.strip()],
        sql=SqlConfig(
            driver=os.getenv("SMARTSUPPLY_SQL_DRIVER", "ODBC Driver 17 for SQL Server"),
            server=os.getenv("SMARTSUPPLY_SQL_SERVER", "localhost"),
            database=os.getenv("SMARTSUPPLY_SQL_DATABASE", "SmartSupply"),
            trusted=_env_bool("SMARTSUPPLY_SQL_TRUSTED", "yes"),
            user=os.getenv("SMARTSUPPLY_SQL_USER") or None,
            password=os.getenv("SMARTSUPPLY_SQL_PASSWORD") or None,
            trust_server_certificate=_env_bool("SMARTSUPPLY_SQL_TRUST_CERT", "yes"),
        ),
    )
