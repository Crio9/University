# uni-personal (MyUni)

Backend MyUni — персональная точка взаимодействия студента с университетом.

Ключевая механика: **собрать → классифицировать → структурировать → сопоставить с контекстом → доставить**.

Реализованные спринты:

- **Sprint 1:** сотрудник создаёт публикации для разных аудиторий → студент регистрируется и заполняет профиль → `GET /api/v1/posts/feed` отдаёт только подходящий контент.
- **Sprint 2:** слой ingestion (`raw_contents`), обновлённые справочники категорий/тегов, сервис нормализации AI-вывода, сохранённые публикации (`user_saved_posts`) и админ-очередь обработки. Prep задания MYUNI-105/96/98/111.

## Стек

- FastAPI
- PostgreSQL
- SQLAlchemy 2
- Alembic
- JWT (python-jose + passlib)

## Быстрый старт

### 1. PostgreSQL

**Вариант A — Docker** (если Docker Desktop / WSL работают):

```bash
docker compose up -d
```

**Вариант B — PostgreSQL для Windows** (если Docker/WSL сломан):

1. Скачайте установщик: https://www.postgresql.org/download/windows/
2. При установке задайте пользователя/пароль (например `uni` / `uni`) и порт `5432`
3. Создайте БД `uni_personal`
4. Пропишите в `.env`:

```env
DATABASE_URL=postgresql+psycopg2://uni:uni@localhost:5432/uni_personal
```

### 2. Python-окружение

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # или cp .env.example .env
```

### 3. Миграции и seed

```bash
alembic upgrade head
python seed.py
```

### 4. Запуск API

```bash
uvicorn app.main:app --reload
```

Swagger: http://127.0.0.1:8000/docs

## Основные эндпоинты

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/health` | healthcheck |
| GET | `/api/v1/tags` | справочник тегов (глобальный словарь) |
| GET | `/api/v1/categories` | справочник категорий |
| POST | `/api/v1/auth/register` | регистрация |
| POST | `/api/v1/auth/login` | логин (form: username/password) |
| GET | `/api/v1/profiles/me` | свой профиль |
| PATCH | `/api/v1/profiles/me/student` | обновить профиль студента |
| POST | `/api/v1/posts` | создать публикацию (staff) |
| GET | `/api/v1/posts/feed` | персональная лента (с флагом `is_saved`) |
| GET | `/api/v1/posts/saved` | сохранённые публикации пользователя |
| POST | `/api/v1/posts/{id}/save` | сохранить публикацию (идемпотентно) |
| DELETE | `/api/v1/posts/{id}/save` | убрать из сохранённых |
| POST | `/api/v1/ingest/raw` | ручной приём сырого контента (staff, идемпотентно по `source_type`+`external_id`) |
| GET | `/api/v1/ingest/raw` | очередь сырых публикаций и их статусы (staff, фильтр `?status=`) |
| POST | `/api/v1/ingest/raw/{id}/retry` | перезапуск обработки (staff) |

## Справочники и классификация

Единый источник истины — [`app/core/dictionaries.py`](app/core/dictionaries.py).

- **Категории (5):** `ACADEMIC`, `ADMINISTRATIVE`, `OPPORTUNITY`, `EVENT`, `NEWS`.
- **Теги (25):** `CAREER`, `INTERNSHIP`, `JOB`, `SCIENCE`, `RESEARCH`, `CONFERENCE`, `SCHOLARSHIP`, `GRANT`, `COMPETITION`, `OLYMPIAD`, `HACKATHON`, `INTERNATIONAL`, `EXCHANGE`, `VOLUNTEERING`, `STUDENT_LIFE`, `SPORT`, `CULTURE`, `SCHEDULE`, `EXAM`, `PRACTICE`, `THESIS`, `DOCUMENTS`, `DORMITORY`, `FINANCE`, `CAMPUS`.
- **Статусы обработки:** `pending`, `processed`, `failed`, `needs_review`.

Пайплайн обработки сырого контента (`app/services/classification.py`):

```
raw content → AI-классификация (плагин) → валидация → нормализация → Post
```

AI-провайдер подключается как адаптер (`Classifier`) в задаче MYUNI-98. Пока он не
подключён, элементы очереди остаются в статусе `pending` — непровалидированный
AI-ответ в нормализованное хранилище не попадает. Нормализация
(`app/services/normalization.py`) сопоставляет свободные строки от AI с каноническим
словарём; неоднозначные значения переводят запись в `needs_review`.

## Seed-пользователи

| Email | Пароль | Роль |
|-------|--------|------|
| `staff@example.com` | `staff123` | staff |
| `student.it@example.com` | `student123` | student (ФИТ, 3 курс) |
| `student.law@example.com` | `student123` | student (Юрфак, 1 курс) |

Также создаются 5 категорий, 25 тегов и 5 демонстрационных публикаций с разным таргетингом. Seed идемпотентен: повторный запуск reconcile-ит справочники, не создавая дубликатов.

## Тесты

```bash
pytest
```

## Структура

```
app/
  main.py
  core/          # settings, security, dictionaries (canonical vocabulary)
  db/            # engine, Base
  models/        # User, profiles, Post, dictionaries, RawContent, saved posts
  schemas/
  api/           # routers
  services/      # auth, feed, ingestion, classification, normalization, saved_posts
  dependencies/
alembic/
seed.py
tests/
```

Дальше без ломки каркаса можно добавить модули «Расписание» и «Обращения», а также
конкретный AI-провайдер для `Classifier`.
