"""
Получение метаданных фильма через kinopoisk.dev (unofficial API).
Бесплатный тариф: 500 запросов/сутки.
Токен получить: https://kinopoisk.dev
"""

import httpx
import logging

from app.core.config import settings
from app.schemas.movie import MovieCreate

logger = logging.getLogger(__name__)


async def fetch_movie_meta(kp_id: int) -> MovieCreate | None:
    url = f"{settings.KINOPOISK_API_URL}/movie/{kp_id}"
    headers = {"X-API-KEY": settings.KINOPOISK_API_TOKEN}

    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(url, headers=headers, timeout=10)
            r.raise_for_status()
            data = r.json()
    except Exception as exc:
        logger.error("Kinopoisk API error for kp_id=%s: %s", kp_id, exc)
        return None

    def _extract_names(items: list[dict], key: str = "name") -> list[str]:
        return [i.get(key, "") for i in (items or []) if i.get(key)]

    def _trailer_url(videos: dict) -> str | None:
        trailers = (videos or {}).get("trailers", [])
        for t in trailers:
            if t.get("site") == "youtube":
                return t.get("url")
        return trailers[0].get("url") if trailers else None

    persons_raw = data.get("persons", [])[:10]
    persons = [
        {
            "id": p.get("id"),
            "name": p.get("name"),
            "photo": p.get("photo"),
            "profession": p.get("profession"),
        }
        for p in persons_raw
    ]

    return MovieCreate(
        kinopoisk_id=data["id"],
        title=data.get("name") or data.get("alternativeName") or "",
        title_en=data.get("alternativeName"),
        type=data.get("type", "FILM").upper(),
        year=data.get("year"),
        description=data.get("description"),
        short_description=data.get("shortDescription"),
        rating_kp=data.get("rating", {}).get("kp"),
        rating_imdb=data.get("rating", {}).get("imdb"),
        votes_kp=data.get("votes", {}).get("kp"),
        poster_url=data.get("poster", {}).get("url"),
        backdrop_url=data.get("backdrop", {}).get("url"),
        trailer_url=_trailer_url(data.get("videos")),
        genres=_extract_names(data.get("genres", [])),
        countries=_extract_names(data.get("countries", [])),
        persons=persons,
        seasons_count=data.get("seasonsCount"),
    )
