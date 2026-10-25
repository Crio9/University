import json
from datetime import timedelta

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.ai_classification import AIClassificationResult
from app.services.ai_classifier import NVIDIAAIProvider


def valid_result(**overrides):
    return dict(
        {
            "category": "OPPORTUNITY",
            "tags": ["CAREER", "INTERNSHIP"],
            "importance": "NORMAL",
            "deadline": "2026-11-15T23:59:59+03:00",
            "target_audience": {
                "faculty": ["ИОТ"],
                "program": [],
                "course": [3, 4],
                "group": [],
            },
            "summary": "Стажировка ИОТ 3–4 курса до 15 ноября.",
            "confidence": 0.93,
        },
        **overrides
    )


@pytest.mark.parametrize(
    "change",
    [
        {"summary": 123},
        {"confidence": 1.1},
        {"category": "UNKNOWN"},
        {"deadline": 1700000000},
        {
            "target_audience": {
                "faculty": [],
                "program": [],
                "course": [True],
                "group": [],
            }
        },
        {"target_audience": {"faculty": [], "program": [], "course": [0], "group": []}},
    ],
)
def test_invalid_contract_is_rejected(change):
    with pytest.raises(ValidationError):
        AIClassificationResult.model_validate(valid_result(**change))


def test_missing_audience_is_not_broadcast():
    payload = valid_result()
    del payload["target_audience"]
    with pytest.raises(ValidationError):
        AIClassificationResult.model_validate(payload)


def test_naive_deadline_uses_university_timezone():
    result = AIClassificationResult.model_validate(
        valid_result(deadline="2026-11-15T23:59:59")
    )
    assert result.deadline.hour == 20
    assert result.deadline.utcoffset() == timedelta(0)


def test_date_only_deadline_ends_at_end_of_university_day():
    result = AIClassificationResult.model_validate(valid_result(deadline="2026-11-15"))
    assert result.deadline.isoformat() == "2026-11-15T20:59:59+00:00"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "model", ["nvidia/nemotron-3.5-lightning-30b-a3b", "custom/model"]
)
async def test_nvidia_request_and_response_contract(monkeypatch, model):
    monkeypatch.setattr(settings, "NVIDIA_API_KEY", "unit-test-key")
    monkeypatch.setattr(settings, "NVIDIA_MODEL", model)

    def respond(request):
        payload = json.loads(request.content)
        assert str(request.url).endswith("/chat/completions")
        assert request.headers["authorization"] == "Bearer unit-test-key"
        assert payload["model"] == settings.NVIDIA_MODEL
        assert payload["response_format"] == {"type": "json_object"}
        if model.startswith("nvidia/nemotron-3.5-"):
            assert payload["chat_template_kwargs"] == {"enable_thinking": False}
        else:
            assert "chat_template_kwargs" not in payload
        assert "CAREER" in payload["messages"][0]["content"]
        user = json.loads(payload["messages"][1]["content"])
        assert user["source_context"]["published_at"] == "2026-10-25T10:00:00Z"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(valid_result())}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        result = await NVIDIAAIProvider(client).classify(
            "Стажировка", "Текст", context={"published_at": "2026-10-25T10:00:00Z"}
        )
    assert result.target_audience.course == [3, 4]
    assert result.confidence == 0.93


@pytest.mark.asyncio
@pytest.mark.parametrize("status,expected_calls", [(503, 2), (429, 2), (401, 1)])
async def test_http_retries_are_bounded(monkeypatch, status, expected_calls):
    monkeypatch.setattr(settings, "NVIDIA_API_KEY", "unit-test-key")
    monkeypatch.setattr(settings, "NVIDIA_MAX_RETRIES", 1)
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(status, json={"error": "test"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await NVIDIAAIProvider(client).classify("title", "text")
    assert len(calls) == expected_calls


@pytest.mark.asyncio
async def test_invalid_nvidia_json_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "NVIDIA_API_KEY", "unit-test-key")
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, json={"choices": [{"message": {"content": "not json"}}]}
        )
    )
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(json.JSONDecodeError):
            await NVIDIAAIProvider(client).classify("title", "text")
