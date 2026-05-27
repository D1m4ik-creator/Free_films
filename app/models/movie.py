from datetime import datetime
from sqlalchemy import (
    Integer, String, Text, Float, DateTime, JSON,
    ForeignKey, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Movie(Base):
    """Фильм / сериал из Кинопоиска."""
    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    kinopoisk_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)

    # Основные поля
    title: Mapped[str] = mapped_column(String(512))
    title_en: Mapped[str | None] = mapped_column(String(512), nullable=True)
    type: Mapped[str] = mapped_column(String(64))          # FILM | TV_SERIES | MINI_SERIES | TV_SHOW
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    short_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Рейтинги
    rating_kp: Mapped[float | None] = mapped_column(Float, nullable=True)
    rating_imdb: Mapped[float | None] = mapped_column(Float, nullable=True)
    votes_kp: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Медиа
    poster_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    backdrop_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    trailer_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Жанры, страны, актёры — храним как JSON массив строк
    genres: Mapped[list | None] = mapped_column(JSON, nullable=True)
    countries: Mapped[list | None] = mapped_column(JSON, nullable=True)
    persons: Mapped[list | None] = mapped_column(JSON, nullable=True)  # топ-10

    # Для сериалов
    seasons_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Связанные плееры
    players: Mapped[list["Player"]] = relationship(
        "Player", back_populates="movie", cascade="all, delete-orphan"
    )


class Player(Base):
    """Iframe-ссылка одного из агрегаторов для конкретного фильма."""
    __tablename__ = "players"
    __table_args__ = (
        UniqueConstraint("movie_id", "source", name="uq_movie_source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"))

    # Название источника: kodik | alloha | videocdn | bazon | iframe_video
    source: Mapped[str] = mapped_column(String(64))
    iframe_url: Mapped[str] = mapped_column(Text)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    movie: Mapped["Movie"] = relationship("Movie", back_populates="players")
