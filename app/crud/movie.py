from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.movie import Movie, Player
from app.schemas.movie import MovieCreate
from app.core.cache import invalidate_movie_cache


# ──────────────────────── Movie ─────────────────────────

async def get_movie_by_kp_id(db: AsyncSession, kp_id: int) -> Movie | None:
    result = await db.execute(
        select(Movie)
        .options(selectinload(Movie.players))
        .where(Movie.kinopoisk_id == kp_id)
    )
    return result.scalar_one_or_none()


async def get_movie_by_id(db: AsyncSession, movie_id: int) -> Movie | None:
    result = await db.execute(
        select(Movie)
        .options(selectinload(Movie.players))
        .where(Movie.id == movie_id)
    )
    return result.scalar_one_or_none()


async def get_movies(
    db: AsyncSession,
    page: int = 1,
    limit: int = 20,
    genre: str | None = None,
    year: int | None = None,
    type_: str | None = None,
    search: str | None = None,
) -> tuple[int, list[Movie]]:
    query = select(Movie)

    if genre:
        query = query.where(Movie.genres.contains([genre]))
    if year:
        query = query.where(Movie.year == year)
    if type_:
        query = query.where(Movie.type == type_)
    if search:
        query = query.where(Movie.title.ilike(f"%{search}%"))

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar_one()

    query = query.offset((page - 1) * limit).limit(limit).order_by(Movie.id.desc())
    result = await db.execute(query)
    movies = result.scalars().all()

    return total, list(movies)


async def upsert_movie(db: AsyncSession, data: MovieCreate) -> Movie:
    """Создаёт или обновляет фильм по kinopoisk_id."""
    movie = await get_movie_by_kp_id(db, data.kinopoisk_id)
    if movie is None:
        movie = Movie(**data.model_dump())
        db.add(movie)
    else:
        for field, value in data.model_dump().items():
            setattr(movie, field, value)
    await db.commit()
    await db.refresh(movie)
    await invalidate_movie_cache()
    return movie


# ──────────────────────── Player ────────────────────────

async def upsert_player(
    db: AsyncSession,
    movie_id: int,
    source: str,
    iframe_url: str,
) -> Player:
    """Создаёт или обновляет iframe-ссылку плеера."""
    result = await db.execute(
        select(Player).where(
            Player.movie_id == movie_id,
            Player.source == source,
        )
    )
    player = result.scalar_one_or_none()
    if player is None:
        player = Player(movie_id=movie_id, source=source, iframe_url=iframe_url)
        db.add(player)
    else:
        player.iframe_url = iframe_url
    await db.commit()
    await db.refresh(player)
    await invalidate_movie_cache()
    return player
