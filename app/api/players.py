"""
Сервис агрегации плееров.

Бесплатные источники (нужны токены — регистрируешься на сайте):
  - Kodik      https://kodikapi.com
  - Alloha     https://alloha.tv
  - VideoCDN   https://videocdn.tv
  - Bazon      https://bhcesh.me
  - iframe.video — публичный, без токена
"""

import asyncio
import logging
from dataclasses import dataclass

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class PlayerResult:
    source: str
    iframe_url: str | None
    error: str | None = None


async def _safe_get(client: httpx.AsyncClient, url: str, **kwargs) -> dict | list | None:
    try:
        r = await client.get(url, timeout=8, **kwargs)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        logger.warning("Player request failed [%s]: %s", url, exc)
        return None


async def fetch_kodik(client: httpx.AsyncClient, kp_id: int) -> PlayerResult:
    if not settings.KODIK_TOKEN:
        return PlayerResult("kodik", None, "no token")
    url = "https://kodikapi.com/search"
    data = await _safe_get(
        client, url,
        params={"token": settings.KODIK_TOKEN, "kinopoisk_id": kp_id, "with_episodes": "false"},
    )
    if data and data.get("results"):
        iframe = data["results"][0].get("link")
        if iframe and not iframe.startswith("http"):
            iframe = "https:" + iframe
        return PlayerResult("kodik", iframe)
    return PlayerResult("kodik", None, "not found")


async def fetch_alloha(client: httpx.AsyncClient, kp_id: int) -> PlayerResult:
    if not settings.ALLOHA_TOKEN:
        return PlayerResult("alloha", None, "no token")
    url = f"https://api.alloha.tv/"
    data = await _safe_get(
        client, url,
        params={"token": settings.ALLOHA_TOKEN, "kp": kp_id},
    )
    if data and data.get("data", {}).get("iframe"):
        return PlayerResult("alloha", data["data"]["iframe"])
    return PlayerResult("alloha", None, "not found")


async def fetch_videocdn(client: httpx.AsyncClient, kp_id: int) -> PlayerResult:
    if not settings.VIDEOCDN_TOKEN:
        return PlayerResult("videocdn", None, "no token")
    url = "https://videocdn.tv/api/short"
    data = await _safe_get(
        client, url,
        params={"api_token": settings.VIDEOCDN_TOKEN, "kinopoisk_id": kp_id},
    )
    if data and data.get("data"):
        iframe = data["data"][0].get("iframe_src")
        return PlayerResult("videocdn", iframe)
    return PlayerResult("videocdn", None, "not found")


async def fetch_bazon(client: httpx.AsyncClient, kp_id: int) -> PlayerResult:
    if not settings.BAZON_TOKEN:
        return PlayerResult("bazon", None, "no token")
    url = "https://api.bhcesh.me/list"
    data = await _safe_get(
        client, url,
        params={"token": settings.BAZON_TOKEN, "kinopoisk_id": kp_id},
    )
    if data and data.get("results"):
        iframe = data["results"][0].get("iframe_url")
        return PlayerResult("bazon", iframe)
    return PlayerResult("bazon", None, "not found")


async def fetch_iframe_video(client: httpx.AsyncClient, kp_id: int) -> PlayerResult:
    """iframe.video — публичный API без токена."""
    url = "https://iframe.video/api/v2/search"
    data = await _safe_get(client, url, params={"kp": kp_id})
    if data and data.get("results"):
        path = data["results"][0].get("path", "")
        iframe = f"https://iframe.video{path}" if path else None
        return PlayerResult("iframe_video", iframe)
    return PlayerResult("iframe_video", None, "not found")


async def fetch_all_players(kp_id: int) -> list[PlayerResult]:
    """Параллельно запрашивает все агрегаторы."""
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            fetch_kodik(client, kp_id),
            fetch_alloha(client, kp_id),
            fetch_videocdn(client, kp_id),
            fetch_bazon(client, kp_id),
            fetch_iframe_video(client, kp_id),
            return_exceptions=False,
        )
    return [r for r in results if r.iframe_url]  # только рабочие
