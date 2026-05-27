# 🎬 Movie API

FastAPI-бэкенд для сайта с фильмами. Метаданные — с kinopoiskapiunofficial.tech, плееры — с 5 бесплатных агрегаторов.

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

### 1️⃣ Локальная разработка (без Docker)

```bash
# Активировать venv
python -m venv venv
venv\Scripts\activate   # Windows

# Установить зависимости
pip install -r requirements.txt

# Запустить только БД через Docker
docker-compose up db -d

# Запустить API
uvicorn app.main:app --reload --port 8000
```

При старте API:
- 📀 Автоматически загружается каталог Alloha (~43k фильмов) **параллельно** с запуском сервера
- 🎬 Фильмы появляются в `/api/v1/movies` по мере загрузки
- ▶️ Каждый фильм уже содержит **готовый iframe плеера** для просмотра

**Доступные URL:**
- Swagger UI: http://localhost:8000/docs
- Фронтенд: http://localhost (если запущен Nginx через docker-compose)
- API: http://localhost:8000/api/v1

### 2️⃣ Через Docker Compose

```bash
docker-compose up -d
```

Это поднимет:
- PostgreSQL на порту 54329
- FastAPI на порту 8000
- Nginx + Frontend на порту 80

---

## Как работает Alloha интеграция

### Архитектура

```
┌─────────────────────┐
│  Alloha Dataset     │  (API-Movies/alloha)
│  (~43k фильмов)     │  index.json + страницы
└──────────┬──────────┘
           │ импорт (фоновый)
           ▼
┌──────────────────────────────┐
│  PostgreSQL                  │
│  ├─ Movies (метаданные)      │
│  └─ Players (iframe ссылки)  │
└──────────┬───────────────────┘
           │ API JSON
           ▼
┌──────────────────────┐
│  Frontend            │  ▶️ Плеер в iframe
│  (Nginx + HTML/JS)   │  ✅ Готов к просмотру
└──────────────────────┘
```

### Что загружается при импорте

Для каждого фильма сохраняется:

| Поле | Источник Alloha | Назначение |
|------|---|---|
| `title` | `name` | Название фильма |
| `kinopoisk_id` | `id_kp` | Идентификатор для фильтров (обязателен) |
| `type` | `category` | FILM / TV_SERIES / CARTOON |
| `year` | `year` | Год выпуска |
| `rating_kp` | `rating_kp` | Рейтинг Kinopoisk |
| `genres` | `genre` (CSV) | Жанры |
| `poster_url` | `poster` | Постер фильма |
| `description` | `description` | Описание |
| **players.iframe_url** | **`iframe` или `translation_iframe`** | **✨ Готовый плеер для просмотра** |

### Статус синхронизации

Во время загрузки каталога можно отслеживать прогресс:

```bash
curl http://localhost:8000/api/v1/movies/alloha/sync/status
```

Ответ:
```json
{
  "running": true,
  "current_page": 125,
  "total_pages": 250,
  "saved": 5432,
  "players_saved": 3210,
  "started_at": "2024-05-28T10:30:45",
  "last_message": "Загружена страница Alloha 125 из 250"
}
```

---

## API Эндпоинты

### Просмотр каталога

```bash
# Список фильмов (с пагинацией)
GET /api/v1/movies?page=1&limit=20

# Поиск по названию
GET /api/v1/movies?search=зелёная миля

# Фильтры: жанр, год, тип
GET /api/v1/movies?genre=драма&year=1999&type=FILM
```

### Получить фильм с плеерами

```bash
# По ID в БД
GET /api/v1/movies/1

# По ID Kinopoisk
GET /api/v1/movies/kp/435
```

Ответ:
```json
{
  "id": 1,
  "kinopoisk_id": 435,
  "title": "Зелёная миля",
  "year": 1999,
  "rating_kp": 9.1,
  "genres": ["драма", "криминал", "фэнтези"],
  "poster_url": "...",
  "players": [
    {
      "id": 1,
      "source": "alloha_dataset",
      "iframe_url": "https://alloha.tv/embed/...",
      "updated_at": "2024-05-28T..."
    }
  ]
}
```

### Статус Alloha синхронизации

```bash
# Текущий статус
GET /api/v1/movies/alloha/sync/status

# Запустить синхронизацию вручную (если была отключена)
POST /api/v1/movies/alloha/sync
```

---

## Конфигурация

### Переменные окружения (`.env`)

```env
# Включить автозагрузку Alloha при старте
ALLOHA_DATASET_SYNC_ENABLED=true

# Максимум страниц для загрузки (0 = все ~250 страниц)
ALLOHA_DATASET_MAX_PAGES=0

# Пауза между запросами (0.05 сек)
ALLOHA_DATASET_REQUEST_DELAY_SECONDS=0.05
```

### Отключить автозагрузку и запускать вручную

```env
ALLOHA_DATASET_SYNC_ENABLED=false
```

Затем вызвать эндпоинт:
```bash
curl -X POST http://localhost:8000/api/v1/movies/alloha/sync
```

---

## Добавление дополнительных плееров

Если получите токены на других плеерах, обновите `.env`:

```env
KODIK_TOKEN=ваш_токен      # Kodik
ALLOHA_TOKEN=ваш_токен     # Alloha  
VIDEOCDN_TOKEN=ваш_токен   # VideoCDN
BAZON_TOKEN=ваш_токен      # Bazon
```

API автоматически будет искать фильмы в этих источниках и добавлять их в `players` каждого фильма.

---

## Примеры использования

### Пример 1: Получить фильм и его плеер

```bash
curl http://localhost:8000/api/v1/movies/kp/435 \
  | jq '.players[0].iframe_url'
```

Результат:
```
"https://alloha.tv/embed/movie/..."
```

### Пример 2: Встроить плеер на сайт

```html
<iframe 
  src="https://alloha.tv/embed/movie/..." 
  width="100%" 
  height="600" 
  allowfullscreen 
  allow="autoplay">
</iframe>
```

## Основные эндпоинты

| Метод | URL | Описание |
|---|---|---|
| `GET` | `/api/v1/movies` | Список фильмов с пагинацией |
| `GET` | `/api/v1/movies/{id}` | Фильм по ID + плееры |
| `GET` | `/api/v1/movies/kp/{kp_id}` | Фильм по Kinopoisk ID + плееры |
| `GET` | `/api/v1/movies/{id}/players` | Плееры фильма |
| `POST` | `/api/v1/movies/{id}/players/refresh` | Обновить плееры |
| `GET` | `/api/v1/movies/alloha/sync/status` | Статус Alloha синхронизации |
| `POST` | `/api/v1/movies/alloha/sync` | Запустить Alloha синхронизацию |

## Пример: получить фильм с плеером

```bash
# По ID Kinopoisk (Зелёная миля)
curl http://localhost:8000/api/v1/movies/kp/435 | jq '.'
```

## Автозагрузка каталога

При старте API автоматически запускается фоновая синхронизация. Сначала она
обходит `GET /api/v2.2/films/collections`, затем дополняет каталог через
`GET /api/v2.2/films`. Сайт продолжает открываться, а каталог появляется по
мере сохранения фильмов в локальную БД.

Настройки в `.env`:

```env
KINOPOISK_STARTUP_SYNC_ENABLED=true
KINOPOISK_STARTUP_SYNC_MAX_PAGES=0
KINOPOISK_SYNC_REQUEST_DELAY_SECONDS=0.25
KINOPOISK_SYNC_ORDER=RATING
KINOPOISK_SYNC_TYPE=
KINOPOISK_SYNC_USE_FILTERS=true
KINOPOISK_SYNC_COLLECTION_TYPES=TOP_POPULAR_ALL,TOP_POPULAR_MOVIES,TOP_250_MOVIES,TOP_250_TV_SHOWS,POPULAR_SERIES,FAMILY,KIDS_ANIMATION_THEME,COMICS_THEME,CATASTROPHE_THEME,LOVE_THEME,ZOMBIE_THEME,VAMPIRE_THEME
KINOPOISK_SYNC_COLLECTION_MAX_PAGES=50
KINOPOISK_SYNC_FETCH_DETAILS=false
KINOPOISK_ENRICH_ON_DETAIL_ENABLED=true
```

`KINOPOISK_STARTUP_SYNC_MAX_PAGES=0` означает пройти все страницы, которые
вернет Kinopoisk для включенных источников. У unofficial API нет одного метода
для выгрузки всей базы: `/api/v2.2/films` официально ограничен 400 фильмами,
поэтому для стартового каталога используются коллекции. Детальная загрузка
каждого фильма выключена по умолчанию, потому что она быстро расходует дневную
квоту API.

Если `KINOPOISK_ENRICH_ON_DETAIL_ENABLED=true`, подробное описание подтягивается
лениво при открытии карточки фильма, если в БД его еще нет.

## Структура ответа `/movies/kp/435`

```json
{
  "id": 1,
  "kinopoisk_id": 435,
  "title": "Зелёная миля",
  "title_en": "The Green Mile",
  "type": "FILM",
  "year": 1999,
  "rating_kp": 9.1,
  "rating_imdb": 8.6,
  "genres": ["драма", "криминал", "фэнтези"],
  "countries": ["США"],
  "poster_url": "https://avatars.mds.yandex.net/get-kinopoisk-image/...",
  "description": "Пожилой мужчина рассказывает...",
  "players": [
    {
      "id": 1,
      "source": "alloha_dataset",
      "iframe_url": "https://alloha.tv/embed/...",
      "updated_at": "2024-05-28T10:30:45.123456"
    }
  ],
  "created_at": "2024-05-28T10:15:30.123456",
  "updated_at": "2024-05-28T10:30:45.123456"
}
```
