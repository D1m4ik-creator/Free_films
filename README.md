# 🎬 Movie API

FastAPI-бэкенд для сайта с фильмами. Метаданные — с kinopoisk.dev, плееры — с 5 бесплатных агрегаторов.

## Стек
- **FastAPI** + **asyncpg** + **SQLAlchemy 2.0** (async)
- **PostgreSQL** (через Docker)
- **httpx** — параллельные запросы к агрегаторам плееров

## Бесплатные плееры (нужна регистрация на сайте)

| Источник | Сайт | Примечание |
|---|---|---|
| Kodik | kodik.info | Самый популярный, огромная база |
| Alloha | alloha.tv | Хорошее качество |
| VideoCDN | videocdn.tv | Стабильный |
| Bazon | bhcesh.me | Резервный |
| iframe.video | iframe.video | **Без токена** |

## Быстрый старт

```bash
# 1. Клонировать / скопировать проект
cp .env.example .env
# Заполнить токены в .env

# 2. Запустить через Docker
docker-compose up -d

# Swagger UI: http://localhost:8000/docs
```

## Локальная разработка (без Docker)

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Запустить только БД через docker
docker-compose up db -d

uvicorn app.main:app --reload
```

## Основные эндпоинты

| Метод | URL | Описание |
|---|---|---|
| `POST` | `/api/v1/movies/fetch` | Скачать фильм по kp_id |
| `GET` | `/api/v1/movies` | Список (фильтры: genre, year, type, search) |
| `GET` | `/api/v1/movies/{id}` | Фильм по внутреннему ID |
| `GET` | `/api/v1/movies/kp/{kp_id}` | Фильм по Kinopoisk ID |
| `GET` | `/api/v1/movies/{id}/players` | Плееры фильма |
| `POST` | `/api/v1/movies/{id}/players/refresh` | Обновить плееры |

## Кэширование

GET-эндпоинты фильмов кэшируются в памяти процесса приложения:

- `GET /api/v1/movies`
- `GET /api/v1/movies/{id}`
- `GET /api/v1/movies/kp/{kp_id}`

Кэш автоматически очищается после загрузки/обновления фильма и после обновления плееров. Настройки:

```env
MOVIE_CACHE_TTL_SECONDS=300
MOVIE_CACHE_MAX_SIZE=512
```

`MOVIE_CACHE_TTL_SECONDS=0` отключает кэш.

## Пример: загрузить фильм

```bash
curl -X POST http://localhost:8000/api/v1/movies/fetch \
  -H "Content-Type: application/json" \
  -d '{"kinopoisk_id": 435, "fetch_players": true}'
```

## Структура ответа `/movies/kp/435`

```json
{
  "id": 1,
  "kinopoisk_id": 435,
  "title": "Зелёная миля",
  "year": 1999,
  "rating_kp": 9.1,
  "genres": ["драма", "криминал", "фэнтези"],
  "players": [
    {"source": "kodik", "iframe_url": "//kodik.info/film/..."},
    {"source": "iframe_video", "iframe_url": "https://iframe.video/..."}
  ]
}
```
