# uni-personal (MyUni)

Backend MyUni — персональная точка взаимодействия студента с университетом.

Ключевая механика: **собрать → классифицировать → структурировать → сопоставить с контекстом → доставить**.

## Стек

- Python 3.12+, FastAPI
- PostgreSQL, SQLAlchemy 2 (async, asyncpg)
- Alembic
- JWT (python-jose), bcrypt
- pytest + pytest-asyncio, SQLite (aiosqlite) для тестов

## Быстрый старт

```bash
docker compose up -d          # PostgreSQL (если есть Docker)
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env

alembic upgrade head
python seed.py
uvicorn app.main:app --reload
```

Swagger: http://127.0.0.1:8000/docs

## Основные эндпоинты

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/health` | healthcheck |
| POST | `/api/v1/auth/register` | регистрация (`student` / `teacher` / `staff`) |
| POST | `/api/v1/auth/login` | логин (JSON: email/password) |
| GET | `/api/v1/profile/me` | профиль текущего пользователя |
| PUT | `/api/v1/profile/student` \| `/teacher` \| `/staff` | обновление профиля |
| GET | `/api/v1/posts/feed` | персональная лента (с флагом `is_saved`) |
| GET | `/api/v1/posts/saved` | сохранённые публикации |
| POST | `/api/v1/posts/{id}/save` | сохранить публикацию (идемпотентно) |
| DELETE | `/api/v1/posts/{id}/save` | убрать из сохранённых |
| GET | `/api/v1/posts` | список публикаций (staff/admin) |
| POST | `/api/v1/posts` | создать публикацию (staff/admin) |
| GET | `/api/v1/posts/{id}` | публикация по id |
| PUT | `/api/v1/posts/{id}` | редактировать (автор/admin) |
| DELETE | `/api/v1/posts/{id}` | удалить (автор/admin) |
| GET | `/api/v1/tags` | справочник тегов |
| GET | `/api/v1/categories` | справочник категорий |
| POST | `/api/v1/ingest/raw` | ручной приём сырого контента (staff/admin, идемпотентно) |
| GET | `/api/v1/ingest/raw` | очередь сырых публикаций (staff/admin, фильтр `?status=`) |
| POST | `/api/v1/ingest/raw/{id}/retry` | перезапуск обработки (staff/admin) |

## Справочники и классификация

Единый источник истины — [`app/core/dictionaries.py`](app/core/dictionaries.py).

- **Категории (5):** `ACADEMIC`, `ADMINISTRATIVE`, `OPPORTUNITY`, `EVENT`, `NEWS`.
- **Теги (25):** `CAREER`, `INTERNSHIP`, `JOB`, `SCIENCE`, `RESEARCH`, `CONFERENCE`,
  `SCHOLARSHIP`, `GRANT`, `COMPETITION`, `OLYMPIAD`, `HACKATHON`, `INTERNATIONAL`,
  `EXCHANGE`, `VOLUNTEERING`, `STUDENT_LIFE`, `SPORT`, `CULTURE`, `SCHEDULE`,
  `EXAM`, `PRACTICE`, `THESIS`, `DOCUMENTS`, `DORMITORY`, `FINANCE`, `CAMPUS`.
- **Статусы обработки:** `pending`, `processed`, `failed`, `needs_review`.

Пайплайн (`app/services/classification.py`):

```
raw content → AI-классификация (плагин) → валидация → нормализация → Post
```

AI-провайдер подключается как адаптер (`Classifier`) в задаче MYUNI-98. Пока он
не подключён, элементы очереди остаются в `pending` — непровалидированный
AI-ответ не попадает в нормализованное хранилище. Нормализация
(`app/services/normalization.py`) сопоставляет свободные строки с каноническим
словарём; неоднозначные значения переводят запись в `needs_review`.

## Seed-пользователи

| Email | Пароль | Роль |
|-------|--------|------|
| `student@uni.test` | `password123` | student (ФИСТ, 2 курс, ПМИ) |
| `teacher@uni.test` | `password123` | teacher |
| `staff@uni.test` | `password123` | staff |

Seed идемпотентен и создаёт 5 категорий, 25 тегов и 5 демонстрационных публикаций.

## Тесты

```bash
pytest
```

## Структура

```
app/
  main.py
  core/          # settings, security, dictionaries (canonical vocabulary)
  db/            # async engine, Base
  models/        # User, profiles, Post, dictionaries, RawContent, saved posts
  schemas/
  api/           # routers
  services/      # auth, profiles, feed, ingestion, classification, normalization, saved_posts
  dependencies/
alembic/
seed.py
tests/
```

## Telegram: загрузка публичных каналов

Telegram является **источником сырых сообщений**, а не готовых `Post`.
Поддерживаются только открытые каналы, для которых доступен `https://t.me/s/<username>`.
Нужны роль `staff`/`admin`, Bearer JWT и применённая миграция `0002`.
Если Telegram блокирует HTML-просмотр, используйте JSON-импорт.

### Синхронизация одного канала

```bash
curl -X POST http://127.0.0.1:8000/api/v1/ingest/sync \
  -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" \
  -d '{"channel":"dstu_live","limit":20}'
```

Несколько каналов (до 20 за запрос, до 50 видимых текстовых постов с каждого):

```json
{"channels": ["dstu_live", "example_channel"], "limit": 20}
```

### Запасной импорт JSON

`POST /api/v1/ingest/import`, например:

```json
{"channel":"dstu_live","messages":[{"message_id":42,"text":"Текст объявления","published_at":"2026-10-22T12:00:00Z"}]}
```

Ответы: `received`, `inserted`, `duplicates`, `channel` и `channels`.
Хранилище: `raw_contents`, `source_type=telegram`,
`external_id=<channel>:<message_id>`, `status=pending`.
Дубликаты не изменяются благодаря уникальному индексу PostgreSQL.
AI-классификация не вызывается при загрузке Telegram: она отдельный этап.

Страница `t.me/s` показывает только ограниченное число последних сообщений;
загрузка полной истории и сообщений из приватных каналов не поддерживается.
`beautifulsoup4` и `httpx` используются для HTML-парсера.
`pytest tests/test_telegram_source.py tests/test_telegram_api.py` проверяет
парсинг, ошибки, права доступа, импорт и идемпотентность без сетевых запросов.

