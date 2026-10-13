# uni-personal

Backend Sprint 1: персональный университетский сервис.

Сценарий спринта: сотрудник создаёт публикации для разных аудиторий → студент регистрируется и заполняет профиль → `GET /api/v1/posts/feed` отдаёт только подходящий контент.

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
| GET | `/api/v1/tags` | справочник тегов |
| GET | `/api/v1/categories` | справочник категорий |
| POST | `/api/v1/auth/register` | регистрация |
| POST | `/api/v1/auth/login` | логин (form: username/password) |
| GET | `/api/v1/profiles/me` | свой профиль |
| PATCH | `/api/v1/profiles/me/student` | обновить профиль студента |
| POST | `/api/v1/posts` | создать публикацию (staff) |
| GET | `/api/v1/posts/feed` | персональная лента |

## Seed-пользователи

| Email | Пароль | Роль |
|-------|--------|------|
| `staff@example.com` | `staff123` | staff |
| `student.it@example.com` | `student123` | student (ФИТ, 3 курс) |
| `student.law@example.com` | `student123` | student (Юрфак, 1 курс) |

Также создаются 3 категории, 10 тегов и 5 публикаций с разным таргетингом.

## Тесты

```bash
pytest
```

## Структура

```
app/
  main.py
  core/          # settings, security
  db/            # engine, Base
  models/        # User, profiles, Post, dictionaries
  schemas/
  api/           # routers
  services/      # auth, feed
  dependencies/
alembic/
seed.py
tests/
```

Дальше без ломки каркаса можно добавить модули «Расписание» и «Обращения».
