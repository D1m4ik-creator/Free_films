from contextlib import asynccontextmanager
import asyncio
import logging
from contextlib import suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db
from app.api.endpoints import router
from app.services.kinopoisk_sync import sync_kinopoisk_catalog
from app.services.alloha_dataset_sync import sync_alloha_dataset

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    sync_tasks: list[asyncio.Task] = []

    # Приоритет 1: Alloha dataset (готовый каталог ~43k фильмов)
    if settings.ALLOHA_DATASET_SYNC_ENABLED:
        task = asyncio.create_task(sync_alloha_dataset())
        app.state.alloha_sync_task = task
        sync_tasks.append(task)
        task.add_done_callback(
            lambda t: (
                logger.error(
                    "Startup Alloha dataset sync failed: %s",
                    t.exception(),
                )
                if not t.cancelled() and t.exception()
                else None
            )
        )

    # Приоритет 2: Kinopoisk каталог
    if settings.KINOPOISK_STARTUP_SYNC_ENABLED:
        task = asyncio.create_task(sync_kinopoisk_catalog())
        app.state.kinopoisk_sync_task = task
        sync_tasks.append(task)
        task.add_done_callback(
            lambda t: (
                logger.error(
                    "Startup Kinopoisk sync failed: %s",
                    t.exception(),
                )
                if not t.cancelled() and t.exception()
                else None
            )
        )

    try:
        yield
    finally:
        for task in sync_tasks:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task


app = FastAPI(
    title="Movie API",
    description="Агрегатор фильмов с плеерами",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")
