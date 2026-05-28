from typing import List

from app.services.player_providers import PROVIDERS


class PlayerService:
    @staticmethod
    def generate_movie_players(movie) -> List[dict]:
        players: List[dict] = []

        for provider in PROVIDERS:
            try:
                url = provider.movie_url(
                    imdb_id=getattr(movie, "imdb_id", None),
                    tmdb_id=getattr(movie, "tmdb_id", None),
                )

                if not url:
                    continue

                players.append(
                    {
                        "source": provider.name,
                        "iframe_url": url,
                    }
                )

            except Exception:
                continue

        return players

    @staticmethod
    def generate_tv_players(movie, season: int, episode: int) -> List[dict]:
        players: List[dict] = []

        for provider in PROVIDERS:
            try:
                url = provider.tv_url(
                    tmdb_id=getattr(movie, "tmdb_id", None),
                    imdb_id=getattr(movie, "imdb_id", None),
                    season=season,
                    episode=episode,
                )

                if not url:
                    continue

                players.append(
                    {
                        "source": provider.name,
                        "iframe_url": url,
                    }
                )

            except Exception:
                continue

        return players


from app.services.player_providers import PROVIDERS


class PlayerService:
    @staticmethod
    def generate_movie_players(movie):
        players = []

        for provider in PROVIDERS:
            try:
                url = provider.movie_url(
                    imdb_id=movie.imdb_id,
                    tmdb_id=movie.tmdb_id,
                )

                if not url:
                    continue

                players.append(
                    {
                        "source": provider.name,
                        "iframe_url": url,
                    }
                )

            except Exception:
                continue

        return players

    @staticmethod
    def generate_tv_players(movie, season: int, episode: int):
        players = []

        for provider in PROVIDERS:
            try:
                url = provider.tv_url(
                    tmdb_id=movie.tmdb_id,
                    imdb_id=movie.imdb_id,
                    season=season,
                    episode=episode,
                )

                if not url:
                    continue

                players.append(
                    {
                        "source": provider.name,
                        "iframe_url": url,
                    }
                )

            except Exception:
                continue

        return players
