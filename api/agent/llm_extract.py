"""주장 후보를 Claim으로 구조화하는 제한된 LLM 실행 계층."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Protocol

from pydantic import Field, model_validator

from naran.contracts import (
    Claim,
    ClaimType,
    ContractModel,
    EntityLevel,
    ExecutionMode,
    OrganizationBoundary,
    Scope,
    Scope2Method,
    ValueBasis,
)


DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_PROMPT_VERSION = "claim-extract-v1"
DEFAULT_SCHEMA_VERSION = "claim-draft-v1"


class ClaimDraft(ContractModel):
    """LLM이 생성할 수 있는 필드만 포함하며 판정 필드는 허용하지 않는다."""

    claim_type: ClaimType
    metric: str = Field(min_length=1)
    value: Decimal | None
    unit: str | None
    value_basis: ValueBasis | None
    period_start: str | None
    period_end: str | None
    baseline_year: int | None = None
    target_year: int | None = None
    scope: Scope | None
    scope2_method: Scope2Method | None
    organization_boundary: OrganizationBoundary | None
    geographic_boundary: str | None
    entity_level: EntityLevel | None
    raw_text: str = Field(min_length=1)
    page: int = Field(ge=1)
    evidence: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def reject_blank_required_text(self) -> "ClaimDraft":
        if any(
            not value.strip()
            for value in (self.metric, self.raw_text, self.evidence)
        ):
            raise ValueError("metric·raw_text·evidence는 공백일 수 없습니다")
        return self


class ClaimDraftBatch(ContractModel):
    claims: list[ClaimDraft]


@dataclass(frozen=True)
class ClaimCacheKey:
    document_hash: str
    report_id: str
    page: int
    model_name: str
    prompt_version: str
    schema_version: str

    @property
    def digest(self) -> str:
        raw = "\x1f".join(
            (
                self.document_hash,
                self.report_id,
                str(self.page),
                self.model_name,
                self.prompt_version,
                self.schema_version,
            )
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class StructuredClaimClient(Protocol):
    @property
    def model_name(self) -> str:
        ...

    @property
    def prompt_version(self) -> str:
        ...

    def extract(
        self,
        *,
        candidate_texts: tuple[str, ...],
        page: int,
        output_schema: dict,
    ) -> str:
        """JSON 문자열 하나를 반환한다."""


class VerifiedClaimCache:
    def __init__(self) -> None:
        self._entries: dict[ClaimCacheKey, tuple[Claim, ...]] = {}

    def put(self, key: ClaimCacheKey, claims: list[Claim]) -> None:
        if key.page < 1:
            raise ValueError("캐시 키 페이지는 1 이상이어야 합니다")
        if any(claim.page != key.page for claim in claims):
            raise ValueError("캐시 키 페이지와 Claim 페이지가 일치해야 합니다")
        if any(claim.report_id != key.report_id for claim in claims):
            raise ValueError("캐시 키 report_id와 Claim report_id가 일치해야 합니다")
        prepared = tuple(
            claim.model_copy(
                update={"extraction_mode": ExecutionMode.VERIFIED_CACHE},
                deep=True,
            )
            for claim in claims
        )
        existing = self._entries.get(key)
        if existing is not None and existing != prepared:
            raise ValueError("같은 키의 검증 캐시를 다른 내용으로 덮어쓸 수 없습니다")
        self._entries[key] = prepared

    def get(self, key: ClaimCacheKey) -> tuple[Claim, ...] | None:
        claims = self._entries.get(key)
        if claims is None:
            return None
        return tuple(claim.model_copy(deep=True) for claim in claims)

    def pages_for(
        self,
        *,
        document_hash: str,
        report_id: str,
        model_name: str = DEFAULT_MODEL,
        prompt_version: str = DEFAULT_PROMPT_VERSION,
        schema_version: str = DEFAULT_SCHEMA_VERSION,
    ) -> tuple[int, ...]:
        return tuple(
            sorted(
                key.page
                for key in self._entries
                if key.document_hash == document_hash
                and key.report_id == report_id
                and key.model_name == model_name
                and key.prompt_version == prompt_version
                and key.schema_version == schema_version
            )
        )

    @classmethod
    def from_fixture_directory(
        cls,
        fixture_directory: str | Path,
        *,
        model_name: str = DEFAULT_MODEL,
        prompt_version: str = DEFAULT_PROMPT_VERSION,
        schema_version: str = DEFAULT_SCHEMA_VERSION,
    ) -> "VerifiedClaimCache":
        cache = cls()
        fixture_path = Path(fixture_directory)
        for path in sorted(fixture_path.glob("sample_case_*.json")):
            case = json.loads(path.read_text(encoding="utf-8"))
            document_hash = case["report"]["file_hash"]
            claims_by_page: dict[int, list[Claim]] = {}
            for raw_claim in case["claims"]:
                claim = Claim.model_validate(raw_claim)
                claims_by_page.setdefault(claim.page, []).append(claim)
            for page, claims in claims_by_page.items():
                cache.put(
                    ClaimCacheKey(
                        document_hash=document_hash,
                        report_id=case["report"]["id"],
                        page=page,
                        model_name=model_name,
                        prompt_version=prompt_version,
                        schema_version=schema_version,
                    ),
                    claims,
                )
        return cache


@dataclass(frozen=True)
class ExtractionResult:
    claims: tuple[Claim, ...]
    execution_mode: ExecutionMode
    cache_key: ClaimCacheKey
    attempts: int
    failure_reason: str | None = None


class ExtractionUnavailableError(RuntimeError):
    """live와 검증 캐시 모두 사용할 수 없을 때 발생한다."""


def _claim_id(report_id: str, page: int, index: int, raw_text: str) -> str:
    suffix = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()[:12]
    return f"claim-{report_id}-{page}-{index}-{suffix}"


def _to_claims(
    batch: ClaimDraftBatch,
    *,
    report_id: str,
    mode: ExecutionMode,
) -> tuple[Claim, ...]:
    return tuple(
        Claim.model_validate(
            {
                **draft.model_dump(mode="python"),
                "id": _claim_id(report_id, draft.page, index, draft.raw_text),
                "report_id": report_id,
                "extraction_mode": mode,
            }
        )
        for index, draft in enumerate(batch.claims, start=1)
    )


def extract_claims(
    *,
    document_hash: str,
    report_id: str,
    page: int,
    candidate_texts: tuple[str, ...],
    mode: ExecutionMode,
    cache: VerifiedClaimCache,
    client: StructuredClaimClient | None = None,
    model_name: str = DEFAULT_MODEL,
    prompt_version: str = DEFAULT_PROMPT_VERSION,
    schema_version: str = DEFAULT_SCHEMA_VERSION,
) -> ExtractionResult:
    """demo 또는 live 실행 후 검증된 Claim만 반환한다."""

    if not isinstance(mode, ExecutionMode):
        raise TypeError("mode는 ExecutionMode여야 합니다")
    if page < 1:
        raise ValueError("page는 1 이상이어야 합니다")
    key = ClaimCacheKey(
        document_hash=document_hash,
        report_id=report_id,
        page=page,
        model_name=model_name,
        prompt_version=prompt_version,
        schema_version=schema_version,
    )
    cached = cache.get(key)
    if mode is ExecutionMode.VERIFIED_CACHE:
        if cached is None:
            raise ExtractionUnavailableError(
                f"검증 캐시가 없습니다: {key.digest}"
            )
        return ExtractionResult(
            claims=cached,
            execution_mode=ExecutionMode.VERIFIED_CACHE,
            cache_key=key,
            attempts=0,
        )
    if mode is ExecutionMode.FALLBACK:
        raise ValueError("fallback은 live 실패 결과로만 생성할 수 있습니다")
    if client is None:
        raise ExtractionUnavailableError("live 실행에 structured output client가 필요합니다")
    if client.model_name != model_name:
        raise ValueError("client 모델명과 캐시 키 모델명이 일치하지 않습니다")
    if client.prompt_version != prompt_version:
        raise ValueError("client 프롬프트 버전과 캐시 키 버전이 일치하지 않습니다")
    if not candidate_texts:
        raise ExtractionUnavailableError("live 추출에 사용할 주장 후보가 없습니다")

    failures: list[str] = []
    for attempt in (1, 2):
        try:
            raw = client.extract(
                candidate_texts=candidate_texts,
                page=page,
                output_schema=ClaimDraftBatch.model_json_schema(),
            )
            batch = ClaimDraftBatch.model_validate_json(raw)
            if any(draft.page != page for draft in batch.claims):
                raise ValueError("요청 페이지와 추출 Claim 페이지가 다릅니다")
            normalized_candidates = tuple(
                " ".join(candidate.split()) for candidate in candidate_texts
            )
            for draft in batch.claims:
                normalized_raw_text = " ".join(draft.raw_text.split())
                if normalized_raw_text not in normalized_candidates:
                    raise ValueError(
                        "추출 Claim 원문이 입력 후보 문장과 정확히 일치하지 않습니다"
                    )
            claims = _to_claims(
                batch,
                report_id=report_id,
                mode=ExecutionMode.LIVE,
            )
            return ExtractionResult(
                claims=claims,
                execution_mode=ExecutionMode.LIVE,
                cache_key=key,
                attempts=attempt,
            )
        except Exception as exc:  # 제공자·JSON·스키마 실패를 같은 재시도 한도로 처리한다.
            failures.append(f"{type(exc).__name__}: {exc}")

    failure_reason = " | ".join(failures)
    if cached is not None:
        fallback_claims = tuple(
            claim.model_copy(update={"extraction_mode": ExecutionMode.FALLBACK})
            for claim in cached
        )
        return ExtractionResult(
            claims=fallback_claims,
            execution_mode=ExecutionMode.FALLBACK,
            cache_key=key,
            attempts=2,
            failure_reason=failure_reason,
        )
    raise ExtractionUnavailableError(
        f"live 추출 2회 실패 및 검증 캐시 없음: {failure_reason}"
    )
