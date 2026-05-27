from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.cache import movie_cache
from app.schemas.movie import (
    AllohaDatasetSyncRequest,
    CatalogSyncRequest,
    FetchRequest,
    MovieOut,
    MovieListItem,
    PaginatedMovies,
    PlayerOut,
)
from app.crud.movie import (
    get_movie_by_id, get_movie_by_kp_id, get_movies, upsert_movie, upsert_player,
)
from app.api.kinopoisk import fetch_movie_meta
from app.api.players import fetch_all_players
from app.services.alloha_dataset_sync import (
    get_alloha_dataset_sync_status,
    sync_alloha_dataset,
)
from app.services.kinopoisk_sync import get_catalog_sync_status, sync_kinopoisk_catalog

router = APIRouter()


# ─────────────────── helpers ───────────────────────────

async def _refresh_players(movie_id: int, kp_id: int, db: AsyncSession):
    """Фоновая задача: обновить список плееров."""
    results = await fetch_all_players(kp_id)
    for r in results:
        await upsert_player(db, movie_id, r.source, r.iframe_url)


async def _enrich_movie_if_needed(movie, db: AsyncSession):
    """Подтягивает описание и подробности только при открытии карточки."""
    if not settings.KINOPOISK_ENRICH_ON_DETAIL_ENABLED:
        return movie
    if movie.description or movie.short_description:
        return movie

    meta = await fetch_movie_meta(movie.kinopoisk_id)
    if meta is None:
        return movie

    await upsert_movie(db, meta)
    refreshed = await get_movie_by_id(db, movie.id)
    return refreshed or movie


# ─────────────────── Fetch & save ──────────────────────

@router.post("/movies/fetch", response_model=MovieOut, summary="Загрузить фильм с Кинопоиска")
async def fetch_and_save(
    body: FetchRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    1. Скачивает метаданные с kinopoiskapiunofficial.tech
    2. Сохраняет / обновляет фильм в БД  
    3. Параллельно запрашивает все плееры-агрегаторы и сохраняет iframe-ссылки
    """
    meta = await fetch_movie_meta(body.kinopoisk_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Фильм не найден в Kinopoisk API")

    movie = await upsert_movie(db, meta)

    if body.fetch_players:
        # Запускаем в фоне, чтобы не задерживать ответ
        background_tasks.add_task(_refresh_players, movie.id, movie.kinopoisk_id, db)

    await db.refresh(movie, ["players"])
    return movie


@router.get("/movies/sync/status", summary="Статус синхронизации каталога Kinopoisk")
async def catalog_sync_status():
    return await get_catalog_sync_status()


@router.post("/movies/sync", summary="Запустить синхронизацию каталога Kinopoisk")
async def start_catalog_sync(
    background_tasks: BackgroundTasks,
    body: CatalogSyncRequest | None = None,
):
    max_pages = body.max_pages if body else None
    status = await get_catalog_sync_status()
    if status.get("running"):
        return status

    background_tasks.add_task(sync_kinopoisk_catalog, max_pages)
    status["running"] = True
    status["last_message"] = "Синхронизация поставлена в очередь"
    return status


@router.get("/movies/alloha/sync/status", summary="Статус синхронизации Alloha dataset")
async def alloha_dataset_sync_status():
    return await get_alloha_dataset_sync_status()


@router.post("/movies/alloha/sync", summary="Запустить синхронизацию Alloha dataset")
async def start_alloha_dataset_sync(
    background_tasks: BackgroundTasks,
    body: AllohaDatasetSyncRequest | None = None,
):
    max_pages = body.max_pages if body else None
    status = await get_alloha_dataset_sync_status()
    if status.get("running"):
        return status

    background_tasks.add_task(sync_alloha_dataset, max_pages)
    status["running"] = True
    status["last_message"] = "Синхронизация Alloha поставлена в очередь"
    return status


# ─────────────────── GET movies ────────────────────────

@router.get("/movies", response_model=PaginatedMovies, summary="Список фильмов")
async def list_movies(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    genre: str | None = Query(None, description="Фильтр по жанру (напр. 'драма')"),
    year: int | None = Query(None),
    type: str | None = Query(None, description="FILM | TV_SERIES | MINI_SERIES"),
    search: str | None = Query(None, description="Поиск по названию"),
    db: AsyncSession = Depends(get_db),
):
    cache_key = ("movies:list", page, limit, genre, year, type, search)
    cached = await movie_cache.get(cache_key)
    if cached is not None:
        return cached

    total, movies = await get_movies(db, page, limit, genre, year, type, search)
    response = PaginatedMovies(
        total=total,
        page=page,
        limit=limit,
        items=[MovieListItem.model_validate(m) for m in movies],
    )
    payload = response.model_dump(mode="json")
    await movie_cache.set(cache_key, payload)
    return payload


@router.get("/movies/{movie_id}", response_model=MovieOut, summary="Фильм по внутреннему ID")
async def get_movie(movie_id: int, db: AsyncSession = Depends(get_db)):
    cache_key = ("movies:detail:id", movie_id)
    cached = await movie_cache.get(cache_key)
    if cached is not None:
        return cached

    movie = await get_movie_by_id(db, movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Фильм не найден")
    movie = await _enrich_movie_if_needed(movie, db)
    payload = MovieOut.model_validate(movie).model_dump(mode="json")
    await movie_cache.set(cache_key, payload)
    return payload


@router.get(
    "/movies/kp/{kp_id}",
    response_model=MovieOut,
    summary="Фильм по Kinopoisk ID",
)
async def get_movie_by_kinopoisk(kp_id: int, db: AsyncSession = Depends(get_db)):
    cache_key = ("movies:detail:kp", kp_id)
    cached = await movie_cache.get(cache_key)
    if cached is not None:
        return cached

    movie = await get_movie_by_kp_id(db, kp_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Фильм не найден")
    movie = await _enrich_movie_if_needed(movie, db)
    payload = MovieOut.model_validate(movie).model_dump(mode="json")
    await movie_cache.set(cache_key, payload)
    return payload


# ─────────────────── Players ───────────────────────────

@router.post(
    "/movies/{movie_id}/players/refresh",
    response_model=list[PlayerOut],
    summary="Обновить плееры вручную",
)
async def refresh_players(movie_id: int, db: AsyncSession = Depends(get_db)):
    """Синхронно запрашивает все агрегаторы и обновляет ссылки в БД."""
    movie = await get_movie_by_id(db, movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Фильм не найден")

    results = await fetch_all_players(movie.kinopoisk_id)
    saved = []
    for r in results:
        p = await upsert_player(db, movie.id, r.source, r.iframe_url)
        saved.append(p)
    return saved


@router.get(
    "/movies/{movie_id}/players",
    response_model=list[PlayerOut],
    summary="Получить плееры фильма",
)
async def get_players(movie_id: int, db: AsyncSession = Depends(get_db)):
    movie = await get_movie_by_id(db, movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Фильм не найден")
    return movie.players
