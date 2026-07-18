from collections.abc import Iterable
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pyodbc

from .config import SqlConfig, get_config


def build_connection_string(cfg: SqlConfig | None = None) -> str:
    cfg = cfg or get_config().sql
    parts = [
        f"DRIVER={{{cfg.driver}}}",
        f"SERVER={cfg.server}",
        f"DATABASE={cfg.database}",
    ]

    if cfg.trusted:
        parts.append("Trusted_Connection=yes")
    else:
        if not cfg.user or not cfg.password:
            raise ValueError("SQL auth wymaga SMARTSUPPLY_SQL_USER i SMARTSUPPLY_SQL_PASSWORD.")
        parts.append(f"UID={cfg.user}")
        parts.append(f"PWD={cfg.password}")

    if cfg.trust_server_certificate:
        parts.append("TrustServerCertificate=yes")

    return ";".join(parts)


@contextmanager
def get_connection():
    conn = pyodbc.connect(build_connection_string(), autocommit=True)
    try:
        yield conn
    finally:
        conn.close()


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def rows_to_dicts(cursor: pyodbc.Cursor) -> list[dict[str, Any]]:
    columns = [column[0] for column in cursor.description or []]
    return [
        {columns[i]: _json_value(value) for i, value in enumerate(row)}
        for row in cursor.fetchall()
    ]


def fetch_all(query: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, *tuple(params))
        return rows_to_dicts(cursor)


def fetch_one(query: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
    rows = fetch_all(query, params)
    return rows[0] if rows else None
