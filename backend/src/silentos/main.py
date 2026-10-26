"""FastAPI application factory and entry point.

Run: uvicorn silentos.main:app --app-dir backend/src --port 8000
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .api.routes import health
from .application import Application
from .config import Settings, load_settings

logger = logging.getLogger("silentos")


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = load_settings(os.environ.get("SILENTOS_CONFIG"))

    logging.basicConfig(level=getattr(logging, settings.logging.level.upper(), logging.INFO))

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("SilentOS %s starting (env=%s)", __version__, settings.app.env)
        yield
        logger.info("SilentOS shutdown complete")

    app = FastAPI(
        title="SilentOS API",
        version=__version__,
        description="Offline-first multimodal assistive communication backend.",
        lifespan=lifespan,
    )
    # Local dashboard dev server only; production serves the built frontend
    # from the same origin, making CORS unnecessary there.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.application = Application(settings)
    app.include_router(health.router)
    return app


app = create_app()
