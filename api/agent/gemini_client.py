"""Gemini REST structured-output 호출 어댑터."""

from __future__ import annotations

import os
import re
from typing import Any

import requests

from api.agent.llm_extract import DEFAULT_MODEL, DEFAULT_PROMPT_VERSION


GEMINI_API_ROOT = "https://generativelanguage.googleapis.com/v1beta"
_SUPPORTED_SCHEMA_KEYS = {
    "$id",
    "$defs",
    "$ref",
    "$anchor",
    "type",
    "format",
    "title",
    "description",
    "enum",
    "items",
    "prefixItems",
    "minItems",
    "maxItems",
    "minimum",
    "maximum",
    "anyOf",
    "oneOf",
    "properties",
    "additionalProperties",
    "required",
}


class GeminiConfigurationError(ValueError):
    pass


class GeminiResponseError(RuntimeError):
    pass


def _supported_schema(schema: Any) -> Any:
    if isinstance(schema, list):
        return [_supported_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    cleaned: dict[str, Any] = {}
    for key, value in schema.items():
        if key not in _SUPPORTED_SCHEMA_KEYS:
            continue
        if key in {"properties", "$defs"}:
            cleaned[key] = {
                name: _supported_schema(child)
                for name, child in value.items()
            }
        else:
            cleaned[key] = _supported_schema(value)
    return cleaned


class GeminiStructuredClaimClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model_name: str | None = None,
        prompt_version: str = DEFAULT_PROMPT_VERSION,
        timeout: float | None = None,
        session: requests.Session | None = None,
    ) -> None:
        resolved_key = api_key or os.getenv("GEMINI_API_KEY")
        resolved_model = model_name or os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
        try:
            resolved_timeout = (
                timeout
                if timeout is not None
                else float(os.getenv("GEMINI_TIMEOUT_SECONDS", "30"))
            )
        except ValueError as exc:
            raise GeminiConfigurationError(
                "GEMINI_TIMEOUT_SECONDS는 숫자여야 합니다"
            ) from exc
        if not resolved_key or not resolved_key.strip():
            raise GeminiConfigurationError("GEMINI_API_KEY가 필요합니다")
        if not re.fullmatch(r"[A-Za-z0-9._-]+", resolved_model):
            raise GeminiConfigurationError("Gemini 모델명이 올바르지 않습니다")
        if not prompt_version.strip():
            raise GeminiConfigurationError("프롬프트 버전이 필요합니다")
        if resolved_timeout <= 0:
            raise GeminiConfigurationError("timeout은 0보다 커야 합니다")
        self._api_key = resolved_key.strip()
        self._model_name = resolved_model
        self._prompt_version = prompt_version
        self._timeout = resolved_timeout
        self._session = session or requests.Session()

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def prompt_version(self) -> str:
        return self._prompt_version

    @property
    def timeout(self) -> float:
        return self._timeout

    def _prompt(self, candidate_texts: tuple[str, ...], page: int) -> str:
        candidates = "\n".join(
            f"[후보 {index}] {text}"
            for index, text in enumerate(candidate_texts, start=1)
        )
        return (
            f"프롬프트 버전: {self.prompt_version}\n"
            f"보고서 PDF 페이지: {page}\n"
            "아래 후보에서 검증 가능한 감축목표 또는 실적주장만 구조화하세요.\n"
            "- raw_text는 후보 문장 하나를 글자 변경 없이 그대로 복사합니다.\n"
            "- 명시되지 않은 값, 범위, 산정 방식은 null로 둡니다.\n"
            "- value에는 반드시 수치 하나만 넣습니다. 여러 연도 값이나 여러 "
            "지표 값을 공백으로 이어 붙이지 않습니다.\n"
            "- 한 표 행에 과거부터 최신 순서의 연도별 값이 함께 있으면 가장 "
            "오른쪽 최신 보고연도 값 하나만 value로 구조화합니다.\n"
            "- 어느 값이 최신 보고연도인지 확정할 수 없으면 해당 행을 "
            "Claim으로 만들지 않습니다.\n"
            "- 판정 상태, 차이, 차이율, 위험도, 위법 여부는 생성하지 않습니다.\n"
            "- page에는 제공된 PDF 페이지 번호만 사용합니다.\n\n"
            f"{candidates}"
        )

    def extract(
        self,
        *,
        candidate_texts: tuple[str, ...],
        page: int,
        output_schema: dict,
    ) -> str:
        url = (
            f"{GEMINI_API_ROOT}/models/"
            f"{self.model_name}:generateContent"
        )
        response = self._session.post(
            url,
            headers={
                "x-goog-api-key": self._api_key,
                "Content-Type": "application/json",
            },
            json={
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {"text": self._prompt(candidate_texts, page)}
                        ],
                    }
                ],
                "generationConfig": {
                    "temperature": 0,
                    "responseFormat": {
                        "text": {
                            # 최신 v1beta responseFormat는 MIME 문자열이 아니라
                            # TextResponseFormat.MimeType enum 이름을 요구한다.
                            "mimeType": "APPLICATION_JSON",
                            "schema": _supported_schema(output_schema),
                        }
                    },
                },
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        try:
            payload: dict[str, Any] = response.json()
            candidates = payload["candidates"]
            text = candidates[0]["content"]["parts"][0]["text"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            block_reason = (
                payload.get("promptFeedback", {}).get("blockReason")
                if "payload" in locals()
                else None
            )
            suffix = f"; blockReason={block_reason}" if block_reason else ""
            raise GeminiResponseError(
                f"Gemini 응답에 structured output text가 없습니다{suffix}"
            ) from exc
        if not isinstance(text, str) or not text.strip():
            raise GeminiResponseError("Gemini structured output이 비어 있습니다")
        return text
