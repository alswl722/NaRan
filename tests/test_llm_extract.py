import json
from decimal import Decimal
from pathlib import Path

import pytest

from api.agent.llm_extract import (
    DEFAULT_MODEL,
    DEFAULT_PROMPT_VERSION,
    DEFAULT_SCHEMA_VERSION,
    ClaimCacheKey,
    ExtractionUnavailableError,
    VerifiedClaimCache,
    extract_claims,
)
from naran.contracts import ExecutionMode


FIXTURES = Path(__file__).parents[1] / "fixtures"


def case(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def cache() -> VerifiedClaimCache:
    return VerifiedClaimCache.from_fixture_directory(FIXTURES)


class SequenceClient:
    def __init__(
        self,
        responses: list[str | Exception],
        *,
        model_name: str = DEFAULT_MODEL,
        prompt_version: str = DEFAULT_PROMPT_VERSION,
    ) -> None:
        self.responses = responses
        self.calls = 0
        self.schemas: list[dict] = []
        self.model_name = model_name
        self.prompt_version = prompt_version

    def extract(self, *, candidate_texts, page, output_schema) -> str:
        self.schemas.append(output_schema)
        response = self.responses[self.calls]
        self.calls += 1
        if isinstance(response, Exception):
            raise response
        return response


def draft_batch(raw_claim: dict, **extra) -> str:
    excluded = {"id", "report_id", "extraction_mode"}
    draft = {key: value for key, value in raw_claim.items() if key not in excluded}
    draft.update(extra)
    return json.dumps({"claims": [draft]}, ensure_ascii=False)


def test_demo_cache_extracts_case_a_without_client_or_api_key() -> None:
    data = case("sample_case_a.json")

    result = extract_claims(
        document_hash=data["report"]["file_hash"],
        report_id=data["report"]["id"],
        page=171,
        candidate_texts=(),
        mode=ExecutionMode.VERIFIED_CACHE,
        cache=cache(),
    )

    assert result.execution_mode is ExecutionMode.VERIFIED_CACHE
    assert result.attempts == 0
    assert result.claims[0].value == Decimal(data["claims"][0]["value"])
    assert result.claims[0].page == 171


def test_cache_key_changes_with_every_version_dimension() -> None:
    base = ClaimCacheKey("sha256:x", "report-x", 1, "model", "prompt", "schema")

    variants = [
        ClaimCacheKey("sha256:y", "report-x", 1, "model", "prompt", "schema"),
        ClaimCacheKey("sha256:x", "report-y", 1, "model", "prompt", "schema"),
        ClaimCacheKey("sha256:x", "report-x", 2, "model", "prompt", "schema"),
        ClaimCacheKey("sha256:x", "report-x", 1, "model-2", "prompt", "schema"),
        ClaimCacheKey("sha256:x", "report-x", 1, "model", "prompt-2", "schema"),
        ClaimCacheKey("sha256:x", "report-x", 1, "model", "prompt", "schema-2"),
    ]

    assert all(variant.digest != base.digest for variant in variants)


def test_prompt_version_change_does_not_reuse_old_cache() -> None:
    data = case("sample_case_b.json")

    with pytest.raises(ExtractionUnavailableError, match="검증 캐시가 없습니다"):
        extract_claims(
            document_hash=data["report"]["file_hash"],
            report_id=data["report"]["id"],
            page=68,
            candidate_texts=(),
            mode=ExecutionMode.VERIFIED_CACHE,
            cache=cache(),
            prompt_version="claim-extract-v2",
        )


def test_invalid_json_is_retried_once_then_live_succeeds() -> None:
    data = case("sample_case_c.json")
    client = SequenceClient(
        ["not-json", draft_batch(data["claims"][0])]
    )

    result = extract_claims(
        document_hash="sha256:live-document",
        report_id=data["report"]["id"],
        page=1,
        candidate_texts=(data["claims"][0]["raw_text"],),
        mode=ExecutionMode.LIVE,
        cache=cache(),
        client=client,
    )

    assert result.execution_mode is ExecutionMode.LIVE
    assert result.attempts == 2
    assert client.calls == 2
    assert result.claims[0].extraction_mode is ExecutionMode.LIVE


def test_llm_cannot_add_verdict_or_difference_fields() -> None:
    data = case("sample_case_c.json")
    invalid = draft_batch(
        data["claims"][0],
        verdict="일치",
        relative_difference_pct="0",
    )
    client = SequenceClient([invalid, invalid])

    with pytest.raises(ExtractionUnavailableError, match="2회 실패"):
        extract_claims(
            document_hash="sha256:no-cache",
            report_id=data["report"]["id"],
            page=1,
            candidate_texts=("배출량 100,000tCO2eq",),
            mode=ExecutionMode.LIVE,
            cache=cache(),
            client=client,
        )

    properties = client.schemas[0]["$defs"]["ClaimDraft"]["properties"]
    assert "verdict" not in properties
    assert "relative_difference_pct" not in properties


def test_provider_failure_is_retried_once() -> None:
    data = case("sample_case_c.json")
    client = SequenceClient(
        [TimeoutError("provider timeout"), draft_batch(data["claims"][0])]
    )

    result = extract_claims(
        document_hash="sha256:live-timeout",
        report_id=data["report"]["id"],
        page=1,
        candidate_texts=(data["claims"][0]["raw_text"],),
        mode=ExecutionMode.LIVE,
        cache=cache(),
        client=client,
    )

    assert result.execution_mode is ExecutionMode.LIVE
    assert result.attempts == 2


def test_hallucinated_raw_text_is_rejected() -> None:
    data = case("sample_case_c.json")
    response = draft_batch(data["claims"][0], raw_text="후보에 없던 문장")
    client = SequenceClient([response, response])

    with pytest.raises(ExtractionUnavailableError, match="원문이 입력 후보"):
        extract_claims(
            document_hash="sha256:no-cache",
            report_id=data["report"]["id"],
            page=1,
            candidate_texts=("실제 후보 문장",),
            mode=ExecutionMode.LIVE,
            cache=cache(),
            client=client,
        )


def test_partial_candidate_text_cannot_validate_longer_generated_quote() -> None:
    data = case("sample_case_c.json")
    response = draft_batch(data["claims"][0])
    client = SequenceClient([response, response])

    with pytest.raises(ExtractionUnavailableError, match="정확히 일치"):
        extract_claims(
            document_hash="sha256:no-cache",
            report_id=data["report"]["id"],
            page=1,
            candidate_texts=("배출량",),
            mode=ExecutionMode.LIVE,
            cache=cache(),
            client=client,
        )


def test_cache_is_isolated_by_report_id() -> None:
    data = case("sample_case_a.json")

    with pytest.raises(ExtractionUnavailableError, match="검증 캐시가 없습니다"):
        extract_claims(
            document_hash=data["report"]["file_hash"],
            report_id="another-report",
            page=171,
            candidate_texts=(),
            mode=ExecutionMode.VERIFIED_CACHE,
            cache=cache(),
        )


def test_returned_claim_mutation_does_not_change_verified_cache() -> None:
    data = case("sample_case_a.json")
    verified_cache = cache()
    first = extract_claims(
        document_hash=data["report"]["file_hash"],
        report_id=data["report"]["id"],
        page=171,
        candidate_texts=(),
        mode=ExecutionMode.VERIFIED_CACHE,
        cache=verified_cache,
    )
    first.claims[0].value = 1

    second = extract_claims(
        document_hash=data["report"]["file_hash"],
        report_id=data["report"]["id"],
        page=171,
        candidate_texts=(),
        mode=ExecutionMode.VERIFIED_CACHE,
        cache=verified_cache,
    )

    assert second.claims[0].value == Decimal(data["claims"][0]["value"])


def test_verified_cache_cannot_be_overwritten_with_different_claims() -> None:
    data = case("sample_case_a.json")
    verified_cache = cache()
    key = ClaimCacheKey(
        data["report"]["file_hash"],
        data["report"]["id"],
        171,
        DEFAULT_MODEL,
        DEFAULT_PROMPT_VERSION,
        DEFAULT_SCHEMA_VERSION,
    )
    existing = list(verified_cache.get(key) or ())
    assert existing
    changed = existing[0].model_copy(update={"value": Decimal("1")})

    with pytest.raises(ValueError, match="덮어쓸 수 없습니다"):
        verified_cache.put(key, [changed])


def test_two_live_failures_use_matching_verified_cache() -> None:
    data = case("sample_case_c.json")
    client = SequenceClient(["bad", "still-bad"])

    result = extract_claims(
        document_hash=data["report"]["file_hash"],
        report_id=data["report"]["id"],
        page=1,
        candidate_texts=("배출량 100,000tCO2eq",),
        mode=ExecutionMode.LIVE,
        cache=cache(),
        client=client,
        model_name=DEFAULT_MODEL,
        prompt_version=DEFAULT_PROMPT_VERSION,
        schema_version=DEFAULT_SCHEMA_VERSION,
    )

    assert result.execution_mode is ExecutionMode.FALLBACK
    assert result.attempts == 2
    assert result.failure_reason
    assert result.claims[0].extraction_mode is ExecutionMode.FALLBACK


def test_fallback_cannot_be_requested_directly() -> None:
    with pytest.raises(ValueError, match="live 실패"):
        extract_claims(
            document_hash="sha256:x",
            report_id="report-x",
            page=1,
            candidate_texts=(),
            mode=ExecutionMode.FALLBACK,
            cache=cache(),
        )
