from typing import List


class PlayerProvider:
    name: str

    def movie_url(self, imdb_id: str | None, tmdb_id: int | None):
        raise NotImplementedError

    def tv_url(
        self,
        tmdb_id: int,
        season: int,
        episode: int,
        imdb_id: str | None = None,
    ):
        raise NotImplementedError


class VidAPIProvider(PlayerProvider):
    name = "VidAPI"

    def movie_url(self, imdb_id: str | None, tmdb_id: int | None):
        if imdb_id:
            return f"https://vixsrc.to/movie/{imdb_id}"

        if tmdb_id:
            return f"https://embed.su/embed/movie/{tmdb_id}"

        return None

    def tv_url(
        self,
        tmdb_id: int,
        season: int,
        episode: int,
        imdb_id: str | None = None,
    ):
        return f"https://embed.su/embed/tv/{tmdb_id}/{season}/{episode}"


class SuperEmbedProvider(PlayerProvider):
    name = "SuperEmbed"

    def movie_url(self, imdb_id: str | None, tmdb_id: int | None):
        if imdb_id:
            return f"https://multiembed.mov/?video_id={imdb_id}&tmdb={tmdb_id}"

        return None

    def tv_url(
        self,
        tmdb_id: int,
        season: int,
        episode: int,
        imdb_id: str | None = None,
    ):
        return f"https://multiembed.mov/?video_id={imdb_id}&tmdb={tmdb_id}&s={season}&e={episode}"


class AutoEmbedProvider(PlayerProvider):
    name = "AutoEmbed"

    def movie_url(self, imdb_id: str | None, tmdb_id: int | None):
        if imdb_id:
            return f"https://player.autoembed.cc/embed/movie/{imdb_id}"

        return None

    def tv_url(
        self,
        tmdb_id: int,
        season: int,
        episode: int,
        imdb_id: str | None = None,
    ):
        if imdb_id:
            return f"https://player.autoembed.cc/embed/tv/{imdb_id}/{season}/{episode}"


PROVIDERS: List[PlayerProvider] = [
    VidAPIProvider(),
    SuperEmbedProvider(),
    AutoEmbedProvider(),
]
from typing import List


class PlayerProvider:
    name: str

    def movie_url(self, imdb_id: str | None, tmdb_id: int | None):
        raise NotImplementedError

    def tv_url(
        self,
        tmdb_id: int,
        season: int,
        episode: int,
        imdb_id: str | None = None,
    ):
        raise NotImplementedError


class VidAPIProvider(PlayerProvider):
    name = "VidAPI"

    def movie_url(self, imdb_id: str | None, tmdb_id: int | None):
        if imdb_id:
            return f"https://vixsrc.to/movie/{imdb_id}"

        if tmdb_id:
            return f"https://embed.su/embed/movie/{tmdb_id}"

        return None

    def tv_url(
        self,
        tmdb_id: int,
        season: int,
        episode: int,
        imdb_id: str | None = None,
    ):
        return f"https://embed.su/embed/tv/{tmdb_id}/{season}/{episode}"


class SuperEmbedProvider(PlayerProvider):
    name = "SuperEmbed"

    def movie_url(self, imdb_id: str | None, tmdb_id: int | None):
        if imdb_id:
            return f"https://multiembed.mov/?video_id={imdb_id}&tmdb={tmdb_id}"

        return None

    def tv_url(
        self,
        tmdb_id: int,
        season: int,
        episode: int,
        imdb_id: str | None = None,
    ):
        return f"https://multiembed.mov/?video_id={imdb_id}&tmdb={tmdb_id}&s={season}&e={episode}"


class AutoEmbedProvider(PlayerProvider):
    name = "AutoEmbed"

    def movie_url(self, imdb_id: str | None, tmdb_id: int | None):
        if imdb_id:
            return f"https://player.autoembed.cc/embed/movie/{imdb_id}"

        return None

    def tv_url(
        self,
        tmdb_id: int,
        season: int,
        episode: int,
        imdb_id: str | None = None,
    ):
        if imdb_id:
            return f"https://player.autoembed.cc/embed/tv/{imdb_id}/{season}/{episode}"

        return None


PROVIDERS: List[PlayerProvider] = [
    VidAPIProvider(),
    SuperEmbedProvider(),
    AutoEmbedProvider(),
]
