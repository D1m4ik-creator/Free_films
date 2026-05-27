import asyncio
import logging
from datetime import datetime
from typing import Any

from app.api.kinopoisk import (
    KinopoiskAPIError,
    fetch_movie_meta,
    fetch_movies_collection_page,
    fetch_movies_page,
)
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.crud.movie import upsert_movie
from app.schemas.movie import MovieCreate

logger = logging.getLogger(__name__)

_sync_lock = asyncio.Lock()
_status_lock = asyncio.Lock()
_status: dict[str, Any] = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "current_page": 0,
    "total_pages": None,
    "total_remote": None,
    "current_source": None,
    "processed": 0,
    "saved": 0,
    "skipped_duplicates": 0,
    "errors": 0,
    "last_error": None,
    "last_message": "Синхронизация еще не запускалась",
}


async def get_catalog_sync_status() -> dict[str, Any]:
    async with _status_lock:
        return dict(_status)


async def _update_status(**changes: Any) -> None:
    async with _status_lock:
        _status.update(changes)


def _csv_values(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


async def _save_movies(
    db,
    movies: list[MovieCreate],
    seen_kp_ids: set[int],
    counters: dict[str, int],
) -> None:
    for movie in movies:
        counters["processed"] += 1
        if movie.kinopoisk_id in seen_kp_ids:
            counters["skipped_duplicates"] += 1
            continue

        seen_kp_ids.add(movie.kinopoisk_id)
        try:
            meta = movie
            if settings.KINOPOISK_SYNC_FETCH_DETAILS:
                meta = await fetch_movie_meta(movie.kinopoisk_id) or movie
            await upsert_movie(db, meta)
            counters["saved"] += 1
        except Exception as exc:
            counters["errors"] += 1
            await db.rollback()
            logger.warning(
                "Failed to save Kinopoisk movie %s: %s",
                movie.kinopoisk_id,
                exc,
            )


async def sync_kinopoisk_catalog(max_pages: int | None = None) -> dict[str, Any]:
    """
    Синхронизирует каталог Kinopoisk в локальную БД.

    Функция безопасна для ручного и startup-запуска: второй параллельный запуск
    не начинает новую загрузку и возвращает текущее состояние.
    """
    if _sync_lock.locked():
        status = await get_catalog_sync_status()
        status["last_message"] = "Синхронизация уже выполняется"
        return status

    async with _sync_lock:
        effective_max_pages = (
            settings.KINOPOISK_STARTUP_SYNC_MAX_PAGES
            if max_pages is None
            else max_pages
        )

        await _update_status(
            running=True,
            started_at=datetime.utcnow(),
            finished_at=None,
            current_page=0,
            total_pages=None,
            total_remote=None,
            current_source=None,
            processed=0,
            saved=0,
            skipped_duplicates=0,
            errors=0,
            last_error=None,
            last_message="Синхронизация запущена",
        )

        if not settings.KINOPOISK_API_TOKEN:
            await _update_status(
                running=False,
                finished_at=datetime.utcnow(),
                last_error="KINOPOISK_API_TOKEN is empty",
                last_message="Синхронизация пропущена: нет токена Kinopoisk API",
            )
            return await get_catalog_sync_status()

        counters = {
            "processed": 0,
            "saved": 0,
            "skipped_duplicates": 0,
            "errors": 0,
        }
        remote_total_pages: int | None = None
        fetched_pages = 0
        seen_kp_ids: set[int] = set()

        def page_budget_reached() -> bool:
            return bool(effective_max_pages and effective_max_pages > 0 and fetched_pages >= effective_max_pages)

        try:
            async with AsyncSessionLocal() as db:
                for collection_type in _csv_values(settings.KINOPOISK_SYNC_COLLECTION_TYPES):
                    page = 1
                    while not page_budget_reached():
                        total_remote, total_pages, movies = await fetch_movies_collection_page(
                            collection_type,
                            page,
                        )
                        fetched_pages += 1
                        collection_pages = min(
                            total_pages,
                            settings.KINOPOISK_SYNC_COLLECTION_MAX_PAGES,
                        )

                        await _update_status(
                            current_source=f"collection:{collection_type}",
                            current_page=page,
                            total_pages=collection_pages,
                            total_remote=total_remote,
                            last_message=(
                                f"Загружена коллекция {collection_type}: "
                                f"страница {page} из {collection_pages}"
                            ),
                        )

                        await _save_movies(db, movies, seen_kp_ids, counters)
                        await _update_status(**counters)

                        if page >= collection_pages:
                            break

                        page += 1
                        if settings.KINOPOISK_SYNC_REQUEST_DELAY_SECONDS > 0:
                            await asyncio.sleep(settings.KINOPOISK_SYNC_REQUEST_DELAY_SECONDS)

                if settings.KINOPOISK_SYNC_USE_FILTERS:
                    page = 1
                    while not page_budget_reached():
                        total_remote, total_pages, movies = await fetch_movies_page(
                            page,
                            order=settings.KINOPOISK_SYNC_ORDER,
                            type_=settings.KINOPOISK_SYNC_TYPE or None,
                        )
                        fetched_pages += 1
                        remote_total_pages = total_pages
                        filter_pages = min(total_pages, 20)

                        await _update_status(
                            current_source="filters",
                            current_page=page,
                            total_pages=filter_pages,
                            total_remote=total_remote,
                            last_message=f"Загружен фильтр: страница {page} из {filter_pages}",
                        )

                        await _save_movies(db, movies, seen_kp_ids, counters)
                        await _update_status(**counters)

                        if page >= filter_pages:
                            break

                        page += 1
                        if settings.KINOPOISK_SYNC_REQUEST_DELAY_SECONDS > 0:
                            await asyncio.sleep(settings.KINOPOISK_SYNC_REQUEST_DELAY_SECONDS)

        except (KinopoiskAPIError, Exception) as exc:
            logger.exception("Kinopoisk catalog sync failed")
            failed_counters = dict(counters)
            failed_counters["errors"] += 1
            await _update_status(
                running=False,
                finished_at=datetime.utcnow(),
                **failed_counters,
                last_error=str(exc),
                last_message="Синхронизация остановлена с ошибкой",
            )
            return await get_catalog_sync_status()

        await _update_status(
            running=False,
            finished_at=datetime.utcnow(),
            current_page=fetched_pages,
            total_pages=(
                effective_max_pages
                if effective_max_pages and effective_max_pages > 0
                else remote_total_pages
            ),
            **counters,
            last_message="Синхронизация завершена",
        )
        return await get_catalog_sync_status()
