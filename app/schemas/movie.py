from datetime import datetime
from pydantic import BaseModel, HttpUrl, Field


# ──────────────────────── Player ────────────────────────

class PlayerBase(BaseModel):
    source: str
    iframe_url: str


class PlayerOut(PlayerBase):
    id: int
    updated_at: datetime

    model_config = {"from_attributes": True}


# ──────────────────────── Movie ─────────────────────────

class MovieBase(BaseModel):
    kinopoisk_id: int
    title: str
    title_en: str | None = None
    type: str = "FILM"
    year: int | None = None
    description: str | None = None
    short_description: str | None = None
    rating_kp: float | None = None
    rating_imdb: float | None = None
    votes_kp: int | None = None
    poster_url: str | None = None
    backdrop_url: str | None = None
    trailer_url: str | None = None
    genres: list[str] | None = None
    countries: list[str] | None = None
    persons: list[dict] | None = None
    seasons_count: int | None = None


class MovieCreate(MovieBase):
    pass


class MovieOut(MovieBase):
    id: int
    players: list[PlayerOut] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MovieListItem(BaseModel):
    """Облегчённая схема для списков (без players и persons)."""
    id: int
    kinopoisk_id: int
    title: str
    title_en: str | None = None
    type: str
    year: int | None = None
    rating_kp: float | None = None
    rating_imdb: float | None = None
    poster_url: str | None = None
    genres: list[str] | None = None

    model_config = {"from_attributes": True}


class PaginatedMovies(BaseModel):
    total: int
    page: int
    limit: int
    items: list[MovieListItem]


# ──────────────────────── Kinopoisk fetch ────────────────

class FetchRequest(BaseModel):
    """Запрос на скачивание данных + плееров по kp_id."""
    kinopoisk_id: int = Field(..., description="ID фильма на Кинопоиске")
    fetch_players: bool = Field(True, description="Искать плееры у агрегаторов")
