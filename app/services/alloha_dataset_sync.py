import asyncio
import logging
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import invalidate_movie_cache
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.movie import Movie, Player
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
    "processed": 0,
    "saved": 0,
    "players_saved": 0,
    "skipped_no_kp": 0,
    "skipped_duplicates": 0,
    "errors": 0,
    "last_error": None,
    "last_message": "Синхронизация Alloha еще не запускалась",
}


async def get_alloha_dataset_sync_status() -> dict[str, Any]:
    async with _status_lock:
        return dict(_status)


async def _update_status(**changes: Any) -> None:
    async with _status_lock:
        _status.update(changes)


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _movie_type(item: dict[str, Any]) -> str:
    category = str(item.get("category") or "").lower()
    category_id = _parse_int(item.get("category_id"))
    if "сериал" in category or category_id == 2:
        return "TV_SERIES"
    if "мульт" in category:
        return "CARTOON"
    return "FILM"


def _persons(item: dict[str, Any]) -> list[dict]:
    persons: list[dict] = []
    for key, profession in (
        ("actors", "актер"),
        ("directors", "режиссер"),
        ("producers", "продюсер"),
    ):
        for name in _split_csv(item.get(key)):
            persons.append({"name": name, "profession": profession})
            if len(persons) >= 10:
                return persons
    return persons


def _first_iframe(item: dict[str, Any]) -> str | None:
    iframe = (item.get("iframe") or "").strip()
    if iframe:
        return iframe

    translations = item.get("translation_iframe")
    if isinstance(translations, dict):
        for translation in translations.values():
            if not isinstance(translation, dict):
                continue
            iframe = (translation.get("iframe") or "").strip()
            if iframe:
                return iframe

    seasons = item.get("seasons")
    if isinstance(seasons, dict):
        for season in seasons.values():
            if not isinstance(season, dict):
                continue
            iframe = (season.get("iframe") or "").strip()
            if iframe:
                return iframe
            episodes = season.get("episodes")
            if not isinstance(episodes, dict):
                continue
            for episode in episodes.values():
                if not isinstance(episode, dict):
                    continue
                iframe = (episode.get("iframe") or "").strip()
                if iframe:
                    return iframe
                episode_translations = episode.get("translation")
                if not isinstance(episode_translations, dict):
                    continue
                for translation in episode_translations.values():
                    if not isinstance(translation, dict):
                        continue
                    iframe = (translation.get("iframe") or "").strip()
                    if iframe:
                        return iframe

    return None


def _movie_from_alloha(item: dict[str, Any]) -> tuple[MovieCreate | None, str | None]:
    kp_id = _parse_int(item.get("id_kp")) or _parse_int(item.get("alternative_id_kp"))
    if not kp_id:
        return None, None

    title = item.get("name") or item.get("original_name") or item.get("alternative_name")
    if not title:
        title = f"Kinopoisk {kp_id}"

    movie = MovieCreate(
        kinopoisk_id=kp_id,
        title=title,
        title_en=item.get("original_name") or item.get("alternative_name"),
        type=_movie_type(item),
        year=_parse_int(item.get("year")),
        description=item.get("description"),
        short_description=None,
        rating_kp=_parse_float(item.get("rating_kp")),
        rating_imdb=_parse_float(item.get("rating_imdb")),
        votes_kp=None,
        poster_url=item.get("poster"),
        backdrop_url=None,
        trailer_url=item.get("iframe_trailer"),
        genres=_split_csv(item.get("genre")),
        countries=_split_csv(item.get("country")),
        persons=_persons(item),
        seasons_count=_parse_int(item.get("seasons_count")),
    )
    return movie, _first_iframe(item)


async def _fetch_json(client: httpx.AsyncClient, url: str) -> Any:
    response = await client.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


async def _save_page(
    db: AsyncSession,
    items: list[dict[str, Any]],
    counters: dict[str, int],
) -> None:
    movies_and_players: list[tuple[MovieCreate, str | None]] = []
    for item in items:
        counters["processed"] += 1
        movie, iframe = _movie_from_alloha(item)
        if movie is None:
            counters["skipped_no_kp"] += 1
            continue
        movies_and_players.append((movie, iframe))

    if not movies_and_players:
        return

    kp_ids = [movie.kinopoisk_id for movie, _ in movies_and_players]
    result = await db.execute(select(Movie).where(Movie.kinopoisk_id.in_(kp_ids)))
    existing_by_kp = {movie.kinopoisk_id: movie for movie in result.scalars().all()}

    touched_movies: list[tuple[Movie, str | None]] = []
    for data, iframe in movies_and_players:
        existing = existing_by_kp.get(data.kinopoisk_id)
        if existing is None:
            movie = Movie(**data.model_dump())
            db.add(movie)
            counters["saved"] += 1
        else:
            movie = existing
            counters["skipped_duplicates"] += 1
            for field, value in data.model_dump().items():
                if value not in (None, [], ""):
                    setattr(movie, field, value)
        touched_movies.append((movie, iframe))

    await db.flush()

    player_rows = [(movie, iframe) for movie, iframe in touched_movies if iframe]
    if player_rows:
        movie_ids = [movie.id for movie, _ in player_rows]
        result = await db.execute(
            select(Player).where(
                Player.movie_id.in_(movie_ids),
                Player.source == settings.ALLOHA_DATASET_PLAYER_SOURCE,
            )
        )
        existing_players = {player.movie_id: player for player in result.scalars().all()}
        for movie, iframe in player_rows:
            player = existing_players.get(movie.id)
            if player is None:
                db.add(
                    Player(
                        movie_id=movie.id,
                        source=settings.ALLOHA_DATASET_PLAYER_SOURCE,
                        iframe_url=iframe,
                    )
                )
            else:
                player.iframe_url = iframe
            counters["players_saved"] += 1

    await db.commit()
    await invalidate_movie_cache()


async def sync_alloha_dataset(max_pages: int | None = None) -> dict[str, Any]:
    if _sync_lock.locked():
        status = await get_alloha_dataset_sync_status()
        status["last_message"] = "Синхронизация Alloha уже выполняется"
        return status

    async with _sync_lock:
        effective_max_pages = settings.ALLOHA_DATASET_MAX_PAGES if max_pages is None else max_pages
        counters = {
            "processed": 0,
            "saved": 0,
            "players_saved": 0,
            "skipped_no_kp": 0,
            "skipped_duplicates": 0,
            "errors": 0,
        }
        await _update_status(
            running=True,
            started_at=datetime.utcnow(),
            finished_at=None,
            current_page=0,
            total_pages=None,
            **counters,
            last_error=None,
            last_message="Синхронизация Alloha запущена",
        )

        try:
            async with httpx.AsyncClient() as client:
                index = await _fetch_json(client, settings.ALLOHA_DATASET_INDEX_URL)
                if not isinstance(index, list):
                    raise RuntimeError("Alloha index.json returned unexpected payload")

                page_urls = [url for url in index if isinstance(url, str)]
                if effective_max_pages and effective_max_pages > 0:
                    page_urls = page_urls[:effective_max_pages]

                await _update_status(total_pages=len(page_urls))

                async with AsyncSessionLocal() as db:
                    for page_number, page_url in enumerate(page_urls, start=1):
                        payload = await _fetch_json(client, page_url)
                        items = payload.get("data") if isinstance(payload, dict) else None
                        if not isinstance(items, list):
                            counters["errors"] += 1
                            await _update_status(**counters, last_error=f"Bad Alloha page: {page_url}")
                            continue

                        await _save_page(db, items, counters)
                        await _update_status(
                            current_page=page_number,
                            **counters,
                            last_message=f"Загружена страница Alloha {page_number} из {len(page_urls)}",
                        )

                        if settings.ALLOHA_DATASET_REQUEST_DELAY_SECONDS > 0:
                            await asyncio.sleep(settings.ALLOHA_DATASET_REQUEST_DELAY_SECONDS)

        except Exception as exc:
            logger.exception("Alloha dataset sync failed")
            counters["errors"] += 1
            await _update_status(
                running=False,
                finished_at=datetime.utcnow(),
                **counters,
                last_error=str(exc),
                last_message="Синхронизация Alloha остановлена с ошибкой",
            )
            return await get_alloha_dataset_sync_status()

        await _update_status(
            running=False,
            finished_at=datetime.utcnow(),
            **counters,
            last_message="Синхронизация Alloha завершена",
        )
        return await get_alloha_dataset_sync_status()
