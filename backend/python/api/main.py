from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_config
from .routers import health, towary


config = get_config()

app = FastAPI(
    title=config.title,
    version=config.version,
    description="API tylko do odczytu dla aplikacji mobilnej SmartSupply.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(towary.router)
