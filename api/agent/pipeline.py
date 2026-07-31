"""검증 fixture를 실제 계약과 규칙 엔진으로 실행하는 사례 파이프라인."""

from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlparse

from api.agent.llm_extract import (
    DEFAULT_MODEL,
    DEFAULT_PROMPT_VERSION,
    DEFAULT_SCHEMA_VERSION,
    ExtractionResult,
    VerifiedClaimCache,
    extract_claims,
)
from api.agent.orchestrator import AnalysisRun, RunLock, analyze_performance
from db.entity_map import DEFAULT_ENTITY_MAP, EntityMap, SourceSystem
from naran.contracts import (
    Claim,
    ClaimType,
    Company,
    ExecutionMode,
    MonitoringCase,
    PublicFact,
    Report,
    ValueBasis,
)


@dataclass(frozen=True)
class CaseAnalysis:
    company: Company
    report: Report
    monitoring_case: MonitoringCase
    extractions: tuple[ExtractionResult, ...]
    public_facts: tuple[PublicFact, ...]
    runs: tuple[AnalysisRun, ...]


def _source_system(source_url: str) -> SourceSystem | None:
    hostname = urlparse(source_url).hostname
    if hostname in {"env-info.kr", "www.env-info.kr"}:
        return SourceSystem.ENV_INFO
    if hostname in {"gir.go.kr", "www.gir.go.kr"}:
        return SourceSystem.GIR
    return None


def _reporting_year(claim: Claim) -> int:
    if not claim.period_start:
        raise ValueError(f"Claim {claim.id}에 보고기간 시작일이 없습니다")
    return int(claim.period_start[:4])


_GHG_METRIC = "온실가스 배출량"
_NON_TOTAL_EMISSION_TERMS = (
    "감축",
    "목표",
    "원단위",
    "집약도",
    "배출원",
    "reduction",
    "reduced",
    "target",
    "intensity",
    "avoided",
    "by source",
    "bau",
)


def _canonical_metric(metric: str) -> str:
    """명시적인 온실가스 배출 실적 동의어만 공통 지표명으로 맞춘다."""

    normalized = re.sub(r"\s+", " ", metric.strip().casefold())
    if any(term in normalized for term in _NON_TOTAL_EMISSION_TERMS):
        return normalized
    if (
        ("온실가스" in normalized and "배출" in normalized)
        or re.search(r"\bghg\s+emissions?\b", normalized)
        or "greenhouse gas emission" in normalized
        or re.search(r"\b(?:direct|indirect)\s+emissions?\b", normalized)
    ):
        return _GHG_METRIC
    return normalized


def _matching_facts(
    claim: Claim,
    public_facts: tuple[PublicFact, ...],
) -> tuple[PublicFact, ...]:
    if claim.claim_type is not ClaimType.PERFORMANCE:
        return ()
    if claim.value_basis is ValueBasis.INTENSITY:
        return ()
    claim_metric = _canonical_metric(claim.metric)
    return tuple(
        fact
        for fact in public_facts
        if _canonical_metric(fact.metric) == claim_metric
        and fact.scope == claim.scope
        and (
            claim.value_basis is None
            or fact.value_basis is None
            or fact.value_basis == claim.value_basis
        )
    )


def analyze_verified_case(
    case_data: dict,
    *,
    cache: VerifiedClaimCache,
    entity_map: EntityMap = DEFAULT_ENTITY_MAP,
    model_name: str = DEFAULT_MODEL,
    prompt_version: str = DEFAULT_PROMPT_VERSION,
    schema_version: str = DEFAULT_SCHEMA_VERSION,
) -> CaseAnalysis:
    """A/B/C fixture를 하드코딩된 판정 없이 전체 규칙 흐름으로 실행한다."""

    company = Company.model_validate(case_data["company"])
    report = Report.model_validate(case_data["report"])
    monitoring_case = MonitoringCase.model_validate(case_data["monitoring_case"])
    if report.company_id != company.id:
        raise ValueError("Report와 Company의 company_id가 일치하지 않습니다")
    if monitoring_case.company_id != company.id:
        raise ValueError("MonitoringCase와 Company의 company_id가 일치하지 않습니다")
    if monitoring_case.report_id != report.id:
        raise ValueError("MonitoringCase와 Report의 report_id가 일치하지 않습니다")

    pages = cache.pages_for(
        document_hash=report.file_hash,
        report_id=report.id,
        model_name=model_name,
        prompt_version=prompt_version,
        schema_version=schema_version,
    )
    if not pages:
        raise ValueError("보고서에 사용할 검증 Claim 캐시가 없습니다")

    extractions = tuple(
        extract_claims(
            document_hash=report.file_hash,
            report_id=report.id,
            page=page,
            candidate_texts=(),
            mode=ExecutionMode.VERIFIED_CACHE,
            cache=cache,
            model_name=model_name,
            prompt_version=prompt_version,
            schema_version=schema_version,
        )
        for page in pages
    )
    return analyze_case_extractions(
        case_data,
        extractions=extractions,
        entity_map=entity_map,
    )


def analyze_case_extractions(
    case_data: dict,
    *,
    extractions: tuple[ExtractionResult, ...],
    entity_map: EntityMap = DEFAULT_ENTITY_MAP,
    skip_unmatched_claims: bool = False,
) -> CaseAnalysis:
    """live 또는 검증 캐시에서 구조화된 Claim을 같은 규칙 엔진으로 분석한다."""

    company = Company.model_validate(case_data["company"])
    report = Report.model_validate(case_data["report"])
    monitoring_case = MonitoringCase.model_validate(case_data["monitoring_case"])
    if report.company_id != company.id:
        raise ValueError("Report와 Company의 company_id가 일치하지 않습니다")
    if monitoring_case.company_id != company.id:
        raise ValueError("MonitoringCase와 Company의 company_id가 일치하지 않습니다")
    if monitoring_case.report_id != report.id:
        raise ValueError("MonitoringCase와 Report의 report_id가 일치하지 않습니다")
    if not extractions:
        raise ValueError("분석할 Claim 추출 결과가 없습니다")

    claims = tuple(
        claim for extraction in extractions for claim in extraction.claims
    )
    if not claims:
        raise ValueError("분석할 Claim이 없습니다")
    claim_ids = [claim.id for claim in claims]
    if len(claim_ids) != len(set(claim_ids)):
        raise ValueError("검증 Claim 캐시에 중복 ID가 있습니다")
    public_facts = tuple(
        PublicFact.model_validate(fact) for fact in case_data["public_facts"]
    )
    fact_ids = [fact.id for fact in public_facts]
    if len(fact_ids) != len(set(fact_ids)):
        raise ValueError("PublicFact에 중복 ID가 있습니다")
    if any(fact.company_id != company.id for fact in public_facts):
        raise ValueError("PublicFact와 Company의 company_id가 일치하지 않습니다")

    runs: list[AnalysisRun] = []
    run_lock = RunLock()
    for claim in claims:
        facts = _matching_facts(claim, public_facts)
        if not facts:
            if skip_unmatched_claims:
                continue
            raise ValueError(f"Claim {claim.id}에 대응하는 PublicFact가 없습니다")
        for fact in facts:
            mapping = None
            source_system = _source_system(fact.source_url)
            if source_system is not None and fact.site_id is not None:
                mapping = entity_map.find(
                    source_system=source_system,
                    source_entity_id=fact.site_id,
                    company_id=fact.company_id,
                    year=_reporting_year(claim),
                )
            run = analyze_performance(
                run_id=f"run-{monitoring_case.id}-{claim.id}-{fact.id}",
                report=report,
                claim=claim,
                public_fact=fact,
                boundary_mapping=mapping,
                run_lock=run_lock,
            )
            runs.append(run)
    return CaseAnalysis(
        company=company,
        report=report,
        monitoring_case=monitoring_case,
        extractions=extractions,
        public_facts=public_facts,
        runs=tuple(runs),
    )
