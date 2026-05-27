"""
Получение метаданных фильма через kinopoiskapiunofficial.tech.
Бесплатный тариф: 500 запросов/сутки, до 20 запросов в секунду.
"""

import asyncio
import logging
import re
from typing import Any

import httpx

from app.core.config import settings
from app.schemas.movie import MovieCreate

logger = logging.getLogger(__name__)


class KinopoiskAPIError(RuntimeError):
    pass


def _headers() -> dict[str, str]:
    return {
        "X-API-KEY": settings.KINOPOISK_API_TOKEN,
        "Content-Type": "application/json",
    }


async def _fetch_json(
    client: httpx.AsyncClient,
    endpoint: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: float = 10,
) -> dict | list:
    r = await client.get(
        f"{settings.KINOPOISK_API_URL}{endpoint}",
        headers=_headers(),
        params=params,
        timeout=timeout,
    )
    if r.status_code != 200:
        logger.error(
            "Kinopoisk API Error (%s): Status %s, Response: %s",
            endpoint,
            r.status_code,
            r.text,
        )
    try:
        r.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise KinopoiskAPIError(f"{endpoint}: HTTP {r.status_code}") from exc
    return r.json()


def _extract_names(items: list[dict] | None, key: str) -> list[str]:
    return [i.get(key, "") for i in (items or []) if i.get(key)]


def _parse_year(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    match = re.search(r"\d{4}", str(value))
    return int(match.group(0)) if match else None


def _parse_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _movie_from_kinopoisk_payload(
    film_data: dict[str, Any],
    *,
    persons: list[dict] | None = None,
    trailer_url: str | None = None,
) -> MovieCreate | None:
    kp_id = film_data.get("kinopoiskId") or film_data.get("filmId")
    if not kp_id:
        return None

    title = (
        film_data.get("nameRu")
        or film_data.get("nameOriginal")
        or film_data.get("nameEn")
        or f"Kinopoisk {kp_id}"
    )

    return MovieCreate(
        kinopoisk_id=int(kp_id),
        title=title,
        title_en=film_data.get("nameOriginal") or film_data.get("nameEn"),
        type=(film_data.get("type") or "FILM").upper(),
        year=_parse_year(film_data.get("year")),
        description=film_data.get("description"),
        short_description=film_data.get("shortDescription"),
        rating_kp=_parse_float(
            film_data.get("ratingKinopoisk")
            or film_data.get("rating")
            or film_data.get("ratingKp")
        ),
        rating_imdb=_parse_float(film_data.get("ratingImdb")),
        votes_kp=_parse_int(
            film_data.get("ratingKinopoiskVoteCount")
            or film_data.get("ratingVoteCount")
        ),
        poster_url=film_data.get("posterUrl") or film_data.get("posterUrlPreview"),
        backdrop_url=film_data.get("coverUrl"),
        trailer_url=trailer_url,
        genres=_extract_names(film_data.get("genres", []), "genre"),
        countries=_extract_names(film_data.get("countries", []), "country"),
        persons=persons,
        seasons_count=_parse_int(film_data.get("seasonsCount")),
    )


def _trailer_url(videos: dict | None) -> str | None:
    if not videos or not videos.get("items"):
        return None
    for t in videos["items"]:
        if t.get("site") == "YOUTUBE" or "youtube" in t.get("url", "").lower():
            return t.get("url")
    return videos["items"][0].get("url")


async def fetch_movie_meta(kp_id: int) -> MovieCreate | None:
    async def _fetch(client: httpx.AsyncClient, endpoint: str):
        """Вспомогательная функция для безопасного запроса."""
        try:
            return await _fetch_json(client, endpoint)
        except Exception as exc:
            logger.error("Error fetching %s: %s", endpoint, exc)
            return None

    async with httpx.AsyncClient() as client:
        # Запрашиваем основу, трейлеры и актеров параллельно!
        film_task = _fetch(client, f"/api/v2.2/films/{kp_id}")
        video_task = _fetch(client, f"/api/v2.2/films/{kp_id}/videos")
        staff_task = _fetch(client, f"/api/v1/staff?filmId={kp_id}")

        film_data, video_data, staff_data = await asyncio.gather(film_task, video_task, staff_task)

    # Если основная инфа не пришла (например, 404), прерываем
    if not film_data:
        return None

    persons = []
    if staff_data:
        # Берем только первых 10 человек
        for p in staff_data[:10]:
            persons.append({
                "id": p.get("staffId"),
                "name": p.get("nameRu") or p.get("nameEn"),
                "photo": p.get("posterUrl"),
                "profession": p.get("professionText"),
            })

    return _movie_from_kinopoisk_payload(
        film_data,
        persons=persons,
        trailer_url=_trailer_url(video_data),
    )


async def fetch_movies_page(
    page: int,
    *,
    order: str | None = None,
    type_: str | None = None,
) -> tuple[int, int, list[MovieCreate]]:
    """
    Загружает одну страницу каталога Kinopoisk.

    Возвращает (total, total_pages, items). Эндпоинт /api/v2.2/films уже
    отдает карточки с основными полями, поэтому массовая синхронизация не
    делает отдельные детальные запросы на каждый фильм.
    """
    if not settings.KINOPOISK_API_TOKEN:
        raise KinopoiskAPIError("Kinopoisk API token is empty")

    params: dict[str, Any] = {"page": page}
    if order:
        params["order"] = order
    if type_:
        params["type"] = type_

    async with httpx.AsyncClient() as client:
        data = await _fetch_json(
            client,
            "/api/v2.2/films",
            params=params,
            timeout=20,
        )

    if not isinstance(data, dict):
        raise KinopoiskAPIError("/api/v2.2/films returned unexpected payload")

    items = []
    for item in data.get("items", []) or []:
        movie = _movie_from_kinopoisk_payload(item)
        if movie is not None:
            items.append(movie)

    return (
        int(data.get("total") or len(items)),
        int(data.get("totalPages") or 1),
        items,
    )


async def fetch_movies_collection_page(
    collection_type: str,
    page: int,
) -> tuple[int, int, list[MovieCreate]]:
    """
    Загружает одну страницу коллекции Kinopoisk.

    В отличие от /api/v2.2/films, коллекции могут отдавать до 50 страниц
    конкретного топа/подборки, поэтому они дают более полный стартовый каталог.
    """
    if not settings.KINOPOISK_API_TOKEN:
        raise KinopoiskAPIError("Kinopoisk API token is empty")

    async with httpx.AsyncClient() as client:
        data = await _fetch_json(
            client,
            "/api/v2.2/films/collections",
            params={"type": collection_type, "page": page},
            timeout=20,
        )

    if not isinstance(data, dict):
        raise KinopoiskAPIError("/api/v2.2/films/collections returned unexpected payload")

    items = []
    for item in data.get("items", []) or []:
        movie = _movie_from_kinopoisk_payload(item)
        if movie is not None:
            items.append(movie)

    total = int(data.get("total") or len(items))
    total_pages = int(data.get("totalPages") or max(1, (total + 19) // 20))
    return total, total_pages, items
