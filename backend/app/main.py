from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api.routes import health, jobs, sources, sync, sync_runs
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.session import SessionLocal
from app.models.source import Source


def ensure_primary_source() -> None:
    """Idempotently seed the Himalayas source row so the demo works out of the box."""
    settings = get_settings()
    with SessionLocal() as db:
        exists = db.scalar(
            select(Source.id).where(Source.name == settings.himalayas_source_name)
        )
        if exists is None:
            db.add(
                Source(
                    name=settings.himalayas_source_name,
                    type=settings.himalayas_source_type,
                    base_url=settings.himalayas_feed_url,
                    enabled=True,
                )
            )
            db.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging(get_settings().log_level)
    ensure_primary_source()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(jobs.router)
    app.include_router(sources.router)
    app.include_router(sync_runs.router)
    app.include_router(sync.router)

    return app


app = create_app()