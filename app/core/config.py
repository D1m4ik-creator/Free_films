from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # База данных
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/moviedb"

    # Kinopoisk API (kinopoisk.dev — бесплатный тариф)
    KINOPOISK_API_TOKEN: str = ""
    KINOPOISK_API_URL: str = "https://api.kinopoisk.dev/v1.4"

    # In-memory cache for movie read endpoints. Set TTL to 0 to disable.
    MOVIE_CACHE_TTL_SECONDS: int = 300
    MOVIE_CACHE_MAX_SIZE: int = 512

    # Токены плееров (получить на сайтах плееров)
    KODIK_TOKEN: str = ""       # kodikapi.com
    ALLOHA_TOKEN: str = ""      # alloha.tv
    VIDEOCDN_TOKEN: str = ""    # videocdn.tv
    BAZON_TOKEN: str = ""       # api.bhcesh.me
    # iframe.video — без токена (публичный)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
