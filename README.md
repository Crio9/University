# uni-personal (MyUni)

Backend MyUni — персональная точка взаимодействия студента с университетом.

Ключевая механика: **собрать → классифицировать → структурировать → сопоставить с контекстом → доставить**.

## Стек

- Python 3.12+, FastAPI
- PostgreSQL, SQLAlchemy 2 (async, asyncpg)
- Alembic
- JWT (python-jose), bcrypt
- pytest + pytest-asyncio, SQLite (aiosqlite) для тестов

## Быстрый старт (Linux, Python 3.12)

Код требует работающий PostgreSQL. Настройки подключения задаются в `.env`
по образцу `.env.example`. Не коммитьте реальный `.env` или пароли.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Если PostgreSQL уже установлен, для значений из `.env.example`
создайте **отдельную локальную БД** `uni_service` и роль `uni`
(пример в `psql` из-под администратора PostgreSQL):

```sql
CREATE ROLE uni LOGIN PASSWORD 'uni';
CREATE DATABASE uni_service OWNER uni;
```

Не выполняйте `CREATE ROLE`/`CREATE DATABASE` повторно, если эти объекты
уже есть. Для существующего пользователя/БД укажите правильные значения
`DATABASE_URL` и `ALEMBIC_DATABASE_URL` в `.env`.

```bash
alembic upgrade head
python seed.py
python -m pytest -q
uvicorn app.main:app --reload
```

Swagger: http://127.0.0.1:8000/docs

CI в `.github/workflows/backend-tests.yml` проверяет миграции, seed и сквозные
API-сценарии на PostgreSQL 16, а также тесты SQLite, клиента NVIDIA и Telegram-парсера.

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
| POST | `/api/v1/ingest/process-pending?limit=20` | обработать накопившиеся pending-записи (staff/admin) |

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

При заданном `NVIDIA_API_KEY` общий обработчик использует NVIDIA NIM через
`RawContentClassifier`. Ответ проходит единую Pydantic-схему, нормализацию
категории/тегов и аудитории. Справочники AI не пополняет: неизвестные значения
дают `needs_review`. Ошибки транспорта/JSON/схемы дают `failed`, исходный текст
остаётся в очереди. `summary`, `ai_confidence`, `raw_content_id` сохраняются в
Post; доступный результат AI — в `RawContent.ai_result`.

Полная аудитория хранится в `Post.target_audience`: списки `faculty`, `program`,
`course`, `group`. OR действует внутри списка, AND — между измерениями. Например,
курсы `[3,4]` допускают оба курса, а непустой `group` ограничивает конкретными
группами. Сопоставление faculty/program/group использует существующие значения
профилей студентов с учётом регистра и пробелов; неизвестная аудитория требует
ручной проверки. Отдельных справочников факультетов/программ/групп пока нет.

Старые одиночные поля таргетинга и старые публикации поддерживаются. Ручные
POST/PUT публикации также принимают `target_audience` со всеми четырьмя списками.
В одном запросе используйте либо этот объект, либо одиночные поля. Изменение
одного старого поля у структурированной публикации сохраняет остальные
ограничения, включая группы.

Миграция `0003_ai_audience` добавляет nullable-поля и сохраняет прежние данные.
Откат не допускает потерю групповых или многозначных ограничений: сначала их
нужно явно преобразовать; представимая одиночная аудитория переносится в старые поля.

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
Нужны роль `staff`/`admin`, Bearer JWT и применённые миграции (`alembic upgrade head`).
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
После фиксации Telegram-сообщений в БД запускается фоновая обработка AI.
HTTP-ответ импорта содержит счётчики сырых сообщений; результат классификации
проверяется через `/ingest/raw`. Без ключа сообщения остаются в `pending`.

Страница `t.me/s` показывает только ограниченное число последних сообщений;
загрузка полной истории и сообщений из приватных каналов не поддерживается.
`beautifulsoup4` и `httpx` используются для HTML-парсера.
`pytest tests/test_telegram_source.py tests/test_telegram_api.py` проверяет
парсинг, ошибки, права доступа, импорт и идемпотентность без сетевых запросов.

## NVIDIA и проверка полного сценария

В локальном `.env` задайте `NVIDIA_API_KEY` и перезапустите API. Остальные
настройки имеют значения по умолчанию из `.env.example`: модель
`meta/llama-3.3-70b-instruct`, timeout 30 секунд, максимум 2 повтора при сетевых
ошибках/429/5xx и до 3 одновременно обрабатываемых сообщений одного пакета.
Ключ не требуется для запуска тестов.

Сначала выполните `alembic upgrade head` и `python seed.py`. После
`POST /ingest/sync` или `/ingest/import` фоновый обработчик сохраняет Post,
полную аудиторию, summary, confidence и происхождение. Повторный импорт не
перезаписывает сообщение; повторная обработка уже созданного Post не вызывает
модель и не создаёт дубль. Время дедлайна без пояса трактуется как московское,
дата без времени — как конец дня; в БД сохраняется UTC.

Чтобы обработать накопившиеся сообщения после настройки ключа или перезапуска:

```bash
curl -X POST 'http://127.0.0.1:8000/api/v1/ingest/process-pending?limit=20' \
  -H 'Authorization: Bearer <TOKEN>'
```

Для `failed`/`needs_review` доступен `/ingest/raw/{id}/retry`. Исходные сообщения
сохраняются до запуска фоновой задачи; незавершённый пакет можно запустить снова.

```bash
python -m pytest -q
# Дополнительно запустить API-сценарии и конкурентную обработку на тестовой PostgreSQL:
TEST_DATABASE_URL=postgresql+asyncpg://uni:uni@localhost:5432/uni_service_test python -m pytest -q
```

PostgreSQL-тесты создают и удаляют собственные временные схемы в указанной
тестовой БД. `tests/test_sprint2_flow.py` проверяет импорт → AI → Post → ленту
студентов обоих курсов → save/saved, исключение чужой аудитории, группы и
конкурентные повторы. NVIDIA в автоматических тестах заменяется MockAIProvider
или HTTP MockTransport; реальные сетевые запросы к модели не выполняются.

