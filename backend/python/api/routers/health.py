from fastapi import APIRouter, HTTPException

from ..config import get_config
from ..db import fetch_one


router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    cfg = get_config()
    try:
        sql_info = fetch_one("SELECT @@VERSION AS Version")
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Brak połączenia z SQL Server: {exc}") from exc

    return {
        "status": "ok",
        "server": cfg.sql.server,
        "database": cfg.sql.database,
        "sql_connected": sql_info is not None,
        "sql_version": sql_info["Version"] if sql_info else None,
    }
