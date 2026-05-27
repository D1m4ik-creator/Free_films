from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # База данных
    DATABASE_URL: str = "postgresql+asyncpg://postgres:L7062006v.@localhost:54329/moviedb"

    # Kinopoisk API Unofficial
    KINOPOISK_API_TOKEN: str = "be3d601e-35cf-4e76-880d-fe3bc496aeea"
    KINOPOISK_API_URL: str = "https://kinopoiskapiunofficial.tech"
    KINOPOISK_STARTUP_SYNC_ENABLED: bool = False
    # 0 means load every page returned by Kinopoisk.
    KINOPOISK_STARTUP_SYNC_MAX_PAGES: int = 0
    KINOPOISK_SYNC_REQUEST_DELAY_SECONDS: float = 0.25
    KINOPOISK_SYNC_ORDER: str = "RATING"
    # Empty value means do not send the type filter and let Kinopoisk return all types.
    KINOPOISK_SYNC_TYPE: str = ""
    KINOPOISK_SYNC_USE_FILTERS: bool = True
    KINOPOISK_SYNC_COLLECTION_TYPES: str = (
        "TOP_POPULAR_ALL,TOP_POPULAR_MOVIES,TOP_250_MOVIES,TOP_250_TV_SHOWS,"
        "POPULAR_SERIES,FAMILY,KIDS_ANIMATION_THEME,COMICS_THEME,"
        "CATASTROPHE_THEME,LOVE_THEME,ZOMBIE_THEME,VAMPIRE_THEME"
    )
    KINOPOISK_SYNC_COLLECTION_MAX_PAGES: int = 50
    # Fetching details adds several requests per film, so keep it off for startup catalog sync.
    KINOPOISK_SYNC_FETCH_DETAILS: bool = False
    KINOPOISK_ENRICH_ON_DETAIL_ENABLED: bool = True

    # Public Alloha dataset by API-Movies. Better startup source for playable catalog.
    ALLOHA_DATASET_SYNC_ENABLED: bool = True
    ALLOHA_DATASET_INDEX_URL: str = "https://api-movies.github.io/alloha/index.json"
    # 0 means load every dataset page.
    ALLOHA_DATASET_MAX_PAGES: int = 0
    ALLOHA_DATASET_REQUEST_DELAY_SECONDS: float = 0.05
    ALLOHA_DATASET_PLAYER_SOURCE: str = "alloha_dataset"

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
