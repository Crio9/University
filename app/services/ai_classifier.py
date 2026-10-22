
import json
from typing import Protocol

import httpx

from app.core.config import settings
from app.schemas.ai_classification import AIClassificationResult


SYSTEM_PROMPT = """
Ты — классификатор публикаций университета ДГТУ.

Твоя задача — анализировать заголовок и текст публикации и возвращать
строго один JSON-объект без Markdown и пояснений.

Категории:
- ACADEMIC — занятия, расписание, экзамены, зачёты, учебный процесс.
- ADMINISTRATIVE — приказы, документы, организационные вопросы.
- OPPORTUNITY — стажировки, гранты, конкурсы, вакансии.
- EVENT — конференции, встречи, концерты, студенческие мероприятия.
- NEWS — общие новости университета.

Важность:
- LOW — необязательная информация.
- NORMAL — обычное объявление.
- HIGH — важный срок, изменение расписания или значимое мероприятие.
- CRITICAL — срочная информация, требующая немедленного внимания.

Правила:
1. Выбирай категорию, соответствующую главной цели публикации.
2. Создавай короткие и понятные теги на русском языке.
3. Напиши краткое описание публикации в поле summary.
4. Если указан конкретный срок, запиши его в deadline в формате ISO 8601.
5. Если срок не указан или его невозможно определить, deadline должен быть null.
6. Не придумывай факультеты, направления, курсы и группы.
7. Если целевая аудитория неизвестна, используй пустые списки.
8. confidence — число от 0 до 1, отражающее уверенность классификации.
9. Не считай дату публикации дедлайном, если текст явно не указывает на срок выполнения.
10. Все поля обязательны, кроме deadline, который может быть null.

Примеры:

Вход:
Заголовок: Изменение расписания
Текст: Завтра первая пара начнётся в 10:00.

Выход:
{
  "category": "ACADEMIC",
  "tags": ["расписание", "занятия"],
  "importance": "HIGH",
  "deadline": null,
  "target_audience": {
    "faculty": [],
    "program": [],
    "course": [],
    "group": []
  },
  "summary": "Первая пара завтра начнётся в 10:00.",
  "confidence": 0.98
}

Вход:
Заголовок: Стажировка для студентов
Текст: Открыт набор на оплачиваемую IT-стажировку. Заявки принимаются до 30 ноября 2026 года.

Выход:
{
  "category": "OPPORTUNITY",
  "tags": ["стажировка", "IT", "карьера"],
  "importance": "HIGH",
  "deadline": "2026-11-30T23:59:00",
  "target_audience": {
    "faculty": [],
    "program": [],
    "course": [],
    "group": []
  },
  "summary": "Открыт набор на оплачиваемую IT-стажировку до 30 ноября 2026 года.",
  "confidence": 0.97
}

Верни JSON со следующими полями:
category, tags, importance, deadline, target_audience, summary, confidence.

target_audience должен содержать:
faculty, program, course, group.
"""


class AIProvider(Protocol):
    async def classify(
        self,
        title: str,
        content: str,
    ) -> AIClassificationResult:
        ...


class NVIDIAAIProvider:
    async def classify(
        self,
        title: str,
        content: str,
    ) -> AIClassificationResult:
        if not settings.NVIDIA_API_KEY:
            raise RuntimeError(
                "Не задан NVIDIA_API_KEY в файле .env"
            )

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{settings.NVIDIA_BASE_URL.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": (
                        f"Bearer {settings.NVIDIA_API_KEY}"
                    ),
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.NVIDIA_MODEL,
                    "messages": [
                        {
                            "role": "system",
                            "content": SYSTEM_PROMPT,
                        },
                        {
                            "role": "user",
                            "content": (
                                f"Заголовок: {title}\n"
                                f"Текст публикации:\n{content}"
                            ),
                        },
                    ],
                    "response_format": {
                        "type": "json_object"
                    },
                    "temperature": 0.1,
                    "max_tokens": 1000,
                },
            )

            response.raise_for_status()
            data = response.json()

        result_json = json.loads(
            data["choices"][0]["message"]["content"]
        )

        return AIClassificationResult.model_validate(result_json)


class MockAIProvider:
    """Тестовый провайдер: не обращается к NVIDIA и сети."""

    async def classify(
        self,
        title: str,
        content: str,
    ) -> AIClassificationResult:
        return AIClassificationResult(
            category="ACADEMIC",
            tags=["учёба", "расписание"],
            importance="NORMAL",
            deadline=None,
            target_audience={
                "faculty": [],
                "program": [],
                "course": [],
                "group": [],
            },
            summary=f"{title}: {content[:150]}",
            confidence=0.95,
        )
