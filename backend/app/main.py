from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import get_database
from app.routers import chats
from app.settings import get_settings

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = get_database()
    await db.init()
    logger.info("db.initialized", url=db.settings.database_url)
    yield
    await db.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(chats.router, prefix="/api")

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/health")
    async def api_health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
