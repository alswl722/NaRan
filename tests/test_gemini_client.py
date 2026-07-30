import json

import pytest
import requests

from api.agent.gemini_client import (
    GeminiConfigurationError,
    GeminiResponseError,
    GeminiStructuredClaimClient,
)
from api.agent.llm_extract import (
    DEFAULT_MODEL,
    DEFAULT_PROMPT_VERSION,
    ClaimDraftBatch,
)


class FakeResponse:
    def __init__(self, payload: dict, *, status_error: Exception | None = None):
        self.payload = payload
        self.status_error = status_error

    def raise_for_status(self) -> None:
        if self.status_error:
            raise self.status_error

    def json(self) -> dict:
        return self.payload


class FakeSession:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.calls: list[dict] = []

    def post(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return self.response


def test_api_key_is_required(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(GeminiConfigurationError, match="GEMINI_API_KEY"):
        GeminiStructuredClaimClient()


def test_model_and_timeout_can_be_loaded_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "env-secret")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test-model")
    monkeypatch.setenv("GEMINI_TIMEOUT_SECONDS", "17.5")

    client = GeminiStructuredClaimClient(
        session=FakeSession(FakeResponse({"candidates": []}))
    )

    assert client.model_name == "gemini-test-model"
    assert client.timeout == 17.5


def test_invalid_environment_timeout_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "env-secret")
    monkeypatch.setenv("GEMINI_TIMEOUT_SECONDS", "not-a-number")

    with pytest.raises(GeminiConfigurationError, match="숫자"):
        GeminiStructuredClaimClient()


def test_structured_output_request_uses_schema_and_safe_prompt() -> None:
    output = json.dumps({"claims": []})
    session = FakeSession(
        FakeResponse(
            {
                "candidates": [
                    {"content": {"parts": [{"text": output}]}}
                ]
            }
        )
    )
    client = GeminiStructuredClaimClient(
        api_key="secret-key",
        session=session,
        timeout=12,
    )
    schema = {"type": "object", "properties": {"claims": {"type": "array"}}}

    result = client.extract(
        candidate_texts=("2024년 배출량은 10tCO2eq입니다.",),
        page=7,
        output_schema=schema,
    )

    assert result == output
    call = session.calls[0]
    assert call["url"].endswith(
        f"/models/{DEFAULT_MODEL}:generateContent"
    )
    assert call["headers"]["x-goog-api-key"] == "secret-key"
    assert call["timeout"] == 12
    config = call["json"]["generationConfig"]
    assert config["temperature"] == 0
    assert config["responseFormat"]["text"]["mimeType"] == "APPLICATION_JSON"
    assert config["responseFormat"]["text"]["schema"] == schema
    prompt = call["json"]["contents"][0]["parts"][0]["text"]
    assert DEFAULT_PROMPT_VERSION in prompt
    assert "판정 상태" in prompt
    assert "글자 변경 없이" in prompt


def test_http_error_is_exposed_for_outer_retry() -> None:
    error = requests.HTTPError("429 Too Many Requests")
    client = GeminiStructuredClaimClient(
        api_key="secret",
        session=FakeSession(FakeResponse({}, status_error=error)),
    )

    with pytest.raises(requests.HTTPError, match="429"):
        client.extract(
            candidate_texts=("후보",),
            page=1,
            output_schema={"type": "object"},
        )


def test_blocked_or_malformed_response_has_visible_reason() -> None:
    client = GeminiStructuredClaimClient(
        api_key="secret",
        session=FakeSession(
            FakeResponse(
                {"promptFeedback": {"blockReason": "SAFETY"}}
            )
        ),
    )

    with pytest.raises(GeminiResponseError, match="SAFETY"):
        client.extract(
            candidate_texts=("후보",),
            page=1,
            output_schema={"type": "object"},
        )


@pytest.mark.parametrize(
    "model",
    ["../models/evil", "https://example.com/model", "model:name"],
)
def test_model_name_cannot_change_request_path(model: str) -> None:
    with pytest.raises(GeminiConfigurationError, match="모델명"):
        GeminiStructuredClaimClient(api_key="secret", model_name=model)


def test_pydantic_schema_is_reduced_to_gemini_supported_subset() -> None:
    session = FakeSession(
        FakeResponse(
            {
                "candidates": [
                    {"content": {"parts": [{"text": "{\"claims\": []}"}]}}
                ]
            }
        )
    )
    client = GeminiStructuredClaimClient(api_key="secret", session=session)

    client.extract(
        candidate_texts=("후보",),
        page=1,
        output_schema=ClaimDraftBatch.model_json_schema(),
    )

    sent = session.calls[0]["json"]["generationConfig"]["responseFormat"][
        "text"
    ]["schema"]

    def schema_keys(value):
        if not isinstance(value, dict):
            return set()
        found = set(value) - set(value.get("properties", {})) - set(
            value.get("$defs", {})
        )
        for key, child in value.items():
            if key in {"properties", "$defs"}:
                for nested in child.values():
                    found |= schema_keys(nested)
            elif isinstance(child, dict):
                found |= schema_keys(child)
            elif isinstance(child, list):
                for nested in child:
                    found |= schema_keys(nested)
        return found

    keys = schema_keys(sent)
    assert "default" not in keys
    assert "minLength" not in keys
    assert "pattern" not in keys
