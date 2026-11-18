# Прототип каталога ДГТУ

Из корня ветки prototype/opportunities-mvp скопируйте .env.example в .env, задайте свой JWT_SECRET, POSTGRES_PASSWORD и ключ NVIDIA для классификации. Для локальной демонстрации:

```bash
docker compose up -d --build
docker compose exec backend alembic upgrade head
docker compose exec backend python seed.py
```

Откройте http://localhost:8000/docs. Демо-учётки seed предназначены для изолированной среды. Для общего сервера используйте собственные пароли, HTTPS и прокси на FastAPI. Все пути ниже имеют префикс /api/v1.

1. POST /auth/register с full_name, email, password. POST /auth/login выдаёт access_token для Authorize. Для студента используйте собственную регистрацию.
2. GET /universities и GET /tags возвращают доступные ID. PUT /profile/student принимает faculty_id, study_program_id, interest_ids и опциональные course, preferred_types (internship, junior_job, hackathon, grant, event). Используйте ID из текущей базы. Темы каталога: BACKEND, FRONTEND, AI_DATA, SECURITY, RESEARCH.
3. Под сотрудником вызовите POST /ingest/sync с {"channel":"dstu_live","limit":5} или /ingest/raw с source_type, source_url и raw_text. Если Telegram недоступен с сервера, используйте /ingest/import или ручной ввод оригинала. Повторный ручной импорт того же URL и типа переиспользует запись. Перезагрузка известного ID сохраняет первую копию текста.
4. GET /staff/opportunities показывает исходный текст, извлечённые ссылки, статус и предложенную разметку. ID карточки равен ID оригинала. При отсутствии ключа разметка вводится вручную. Названия тем и типов перечислены выше.
5. PATCH /staff/opportunities/{id} принимает только изменившиеся поля. Для публикации проверьте существование оригинала и следующего шага, укажите status=published, kind=open_call или announcement, title, summary, type, format, topics и способ участия (action_url, contact или instructions_in_source=true). Для очной/гибридной карточки укажите city=Ростов-на-Дону. Нужна хотя бы одна будущая дата из deadline, event_start, event_end, review_by. Для бессрочного набора укажите review_by. Все даты со смещением часового пояса. Итоги, закрытые и неподтверждённые записи оставляйте в draft, rejected или archived.
6. Под студентом GET /opportunities?view=personalized возвращает items и profile_complete. GET /opportunities?view=all показывает общий каталог. Для фильтрации используйте type, offset и limit. GET /opportunities/{id} отдаёт детали. В поле skills передаются навыки из текста. Смена интересов и новый GET сразу меняют порядок.
7. Для показа сравните три профиля с одним направлением и разными интересами. Проверьте источник каждой карточки. Данные учебного seed для старой ленты не наполняют новый каталог.

Реальные материалы для проверки импорта: https://t.me/dstu_live, https://t.me/rndtechevents, https://t.me/fasietalks. Проверяйте даты и доступность участия. Например, осенний хакатон Ростова 23–25 октября 2026 уже завершён: его отчёт должен остаться вне активного каталога. Для федерального гранта «Студенческий стартап» сверяйте условия текущей очереди на https://fasie.ru/studstartup/.

Для проверки обеих СУБД: TEST_DATABASE_URL должен указывать на отдельную тестовую PostgreSQL с правом создания схем. Запуск: python -m pytest -q. Для проверки реальной модели задайте NVIDIA_API_KEY и пройдите шаги 3–5. Тестовый провайдер воспроизводит ответы локально.

Чтобы проверить API на содержательном примере, вставьте examples/student-startup-import.json в POST /ingest/raw под staff. Это ручной пересказ объявления со ссылками на программу и публикацию вуза. Проверьте условия в оригинале перед публикацией. Материал содержит абсолютный дедлайн и должен исчезнуть из активного каталога после 1 декабря 2026 в 10:00 МСК.
