# Обновление проекта Free_films

## Что будет реализовано

В проект добавляется:

- fallback система iframe плееров
- поддержка:
  - VidAPI
  - SuperEmbed
  - AutoEmbed
- динамическая генерация player url
- переключение серверов на frontend
- защита от пустых iframe
- хранение imdb/tmdb id
- нормальная архитектура providers

---

# 1. Создать файл app/services/player_providers.py

```python
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
        return (
            f"https://embed.su/embed/tv/{tmdb_id}/{season}/{episode}"
        )


class SuperEmbedProvider(PlayerProvider):
    name = "SuperEmbed"

    def movie_url(self, imdb_id: str | None, tmdb_id: int | None):
        if imdb_id:
            return (
                f"https://multiembed.mov/?video_id={imdb_id}&tmdb={tmdb_id}"
            )

        return None

    def tv_url(
        self,
        tmdb_id: int,
        season: int,
        episode: int,
        imdb_id: str | None = None,
    ):
        return (
            f"https://multiembed.mov/?video_id={imdb_id}&tmdb={tmdb_id}&s={season}&e={episode}"
        )


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
            return (
                f"https://player.autoembed.cc/embed/tv/{imdb_id}/{season}/{episode}"
            )

        return None


PROVIDERS: List[PlayerProvider] = [
    VidAPIProvider(),
    SuperEmbedProvider(),
    AutoEmbedProvider(),
]
```

---

# 2. Обновить модель Movie

Файл:

```text
app/models/movie.py
```

Добавить:

```python
imdb_id = Column(String, nullable=True, index=True)
tmdb_id = Column(Integer, nullable=True, index=True)
```

После этого:

```bash
docker compose exec backend alembic revision --autogenerate -m "add imdb tmdb ids"

docker compose exec backend alembic upgrade head
```

---

# 3. Добавить генерацию providers

Создать файл:

```text
app/services/player_service.py
```

```python
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
```

---

# 4. Обновить API фильма

Файл:

```text
app/api/v1/movies.py
```

В endpoint фильма:

```python
from app.services.player_service import PlayerService
```

Заменить старую логику players:

```python
players = PlayerService.generate_movie_players(movie)
```

И возвращать:

```python
return {
    "id": movie.id,
    "title": movie.title,
    "year": movie.year,
    "poster_url": movie.poster_url,
    "description": movie.description,
    "players": players,
}
```

---

# 5. Добавить fallback iframe frontend

Файл:

```text
frontend/js/movie.js
```

Полностью заменить player rendering:

```javascript
const iframe = document.getElementById("movie-player")
const serversContainer = document.getElementById("servers")

function loadPlayer(url) {
    iframe.src = url
}

function renderPlayers(players) {
    serversContainer.innerHTML = ""

    if (!players || players.length === 0) {
        serversContainer.innerHTML = `
            <div class="no-players">
                Плееры временно недоступны
            </div>
        `

        return
    }

    players.forEach((player, index) => {
        const button = document.createElement("button")

        button.className = "server-button"
        button.innerText = player.source

        button.onclick = () => {
            loadPlayer(player.iframe_url)
        }

        serversContainer.appendChild(button)

        if (index === 0) {
            loadPlayer(player.iframe_url)
        }
    })
}
```

---

# 6. HTML для player switcher

Файл:

```text
frontend/movie.html
```

Добавить:

```html
<div class="servers" id="servers"></div>

<iframe
    id="movie-player"
    width="100%"
    height="700"
    allowfullscreen
    allow="autoplay; fullscreen"
    frameborder="0"
></iframe>
```

---

# 7. CSS для кнопок серверов

Файл:

```text
frontend/css/movie.css
```

```css
.servers {
    display: flex;
    gap: 10px;
    margin-bottom: 20px;
    flex-wrap: wrap;
}

.server-button {
    border: none;
    background: #181818;
    color: white;
    padding: 10px 18px;
    border-radius: 10px;
    cursor: pointer;
    transition: 0.2s;
}

.server-button:hover {
    transform: scale(1.03);
}

#movie-player {
    border-radius: 14px;
    background: black;
}
```

---

# 8. Исправить главную архитектурную проблему

Сейчас у тебя проект хранит iframe в базе.

Это плохая архитектура для современных агрегаторов.

Почему:

- домены меняются
- iframe протухают
- Cloudflare блокирует старые ссылки
- providers обновляют роуты

Правильнее:

- хранить только imdb/tmdb
- iframe генерировать динамически
- providers держать в одном месте

То есть:

❌ Плохо:

```python
iframe_url = "https://old-provider.com/embed/..."
```

✅ Правильно:

```python
provider.movie_url(movie.imdb_id)
```

---

# 9. Добавить авто fallback если iframe умер

В frontend:

```javascript
let currentPlayer = 0
let allPlayers = []

iframe.onerror = () => {
    currentPlayer++

    if (currentPlayer < allPlayers.length) {
        iframe.src = allPlayers[currentPlayer].iframe_url
    }
}
```

И:

```javascript
allPlayers = players
```

внутри renderPlayers.

---

# 10. Что желательно сделать дальше

Следующий уровень проекта:

- Redis cache
- async health check providers
- proxy backend
- HLS support
- anti-ad overlay
- Cloudflare reverse proxy
- TMDB trending API
- watch history
- continue watching
- subtitles
- quality selector
- episodes selector

---

# 11. Самая важная рекомендация

Не делай зависимость от одного агрегатора.

В 2026 почти все бесплатные providers:

- падают
- меняют домены
- ставят anti-bot
- блокируют iframe

Поэтому multi-provider architecture — обязательна.

Именно так сейчас работают почти все movie streaming сайты.

