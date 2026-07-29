"""나란 SQLAlchemy ORM 모델.

naran/contracts.py의 Pydantic 계약과 필드를 대응시킨다. 여기 정의된 테이블은
개발계획 Step 5의 테이블 목록(보고서/추출 텍스트/주장/공개 데이터/기업·사업장
매핑/비교 가능성 결과/나란 결과/목표 추적 결과/사후관리 건/담당자 검토/이력)을
따른다.

Verdict와 HumanReview는 서로 다른 테이블로 분리해 저장한다 — 담당자 조치가
AI 분석 상태를 덮어쓰지 않는다는 원칙(claude.md 6절, 10절)을 스키마 수준에서
강제하기 위함이다.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    legal_name: Mapped[str] = mapped_column(String, nullable=False)
    identifiers: Mapped[dict] = mapped_column(JSON, default=dict)
    aliases: Mapped[list] = mapped_column(JSON, default=list)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    reporting_year: Mapped[int] = mapped_column(nullable=False)
    file_hash: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str] = mapped_column(String, nullable=False)


class ReportPage(Base):
    """PDF 페이지별 추출 텍스트. 원문 위치를 보존한다 (claude.md 11절 db/parser.py)."""

    __tablename__ = "report_pages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id"), nullable=False)
    page: Mapped[int] = mapped_column(nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    extraction_failed: Mapped[bool] = mapped_column(Boolean, default=False)
    failure_reason: Mapped[str | None] = mapped_column(String, nullable=True)


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id"), nullable=False)
    claim_type: Mapped[str] = mapped_column(String, nullable=False)
    metric: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[str | None] = mapped_column(Numeric, nullable=True)
    unit: Mapped[str | None] = mapped_column(String, nullable=True)
    value_basis: Mapped[str | None] = mapped_column(String, nullable=True)
    period_start: Mapped[str | None] = mapped_column(String, nullable=True)
    period_end: Mapped[str | None] = mapped_column(String, nullable=True)
    baseline_year: Mapped[int | None] = mapped_column(nullable=True)
    target_year: Mapped[int | None] = mapped_column(nullable=True)
    scope: Mapped[str | None] = mapped_column(String, nullable=True)
    scope2_method: Mapped[str | None] = mapped_column(String, nullable=True)
    organization_boundary: Mapped[str | None] = mapped_column(String, nullable=True)
    geographic_boundary: Mapped[str | None] = mapped_column(String, nullable=True)
    entity_level: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    page: Mapped[int] = mapped_column(nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False)
    extraction_mode: Mapped[str] = mapped_column(String, nullable=False)


class PublicFact(Base):
    __tablename__ = "public_facts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), nullable=False)
    site_id: Mapped[str | None] = mapped_column(String, nullable=True)
    entity_level: Mapped[str] = mapped_column(String, nullable=False)
    metric: Mapped[str] = mapped_column(String, nullable=False)
    raw_value: Mapped[str | None] = mapped_column(Numeric, nullable=True)
    normalized_value: Mapped[str | None] = mapped_column(Numeric, nullable=True)
    unit: Mapped[str | None] = mapped_column(String, nullable=True)
    value_basis: Mapped[str | None] = mapped_column(String, nullable=True)
    period_start: Mapped[str | None] = mapped_column(String, nullable=True)
    period_end: Mapped[str | None] = mapped_column(String, nullable=True)
    scope: Mapped[str | None] = mapped_column(String, nullable=True)
    scope2_method: Mapped[str | None] = mapped_column(String, nullable=True)
    organization_boundary: Mapped[str | None] = mapped_column(String, nullable=True)
    geographic_boundary: Mapped[str | None] = mapped_column(String, nullable=True)
    display_decimal_places: Mapped[int | None] = mapped_column(nullable=True)
    display_rule: Mapped[str | None] = mapped_column(String, nullable=True)
    disclosure_duty: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_hash: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[str] = mapped_column(String, nullable=False)


class EntityMapping(Base):
    """법인과 대표·개별 사업장 식별자의 명시적 매핑 (db/entity_map.py 대응)."""

    __tablename__ = "entity_mappings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), nullable=False)
    source_system: Mapped[str] = mapped_column(String, nullable=False)
    source_entity_id: Mapped[str] = mapped_column(String, nullable=False)
    year: Mapped[int] = mapped_column(nullable=False)
    boundary_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class ComparabilityResultRecord(Base):
    __tablename__ = "comparability_results"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"), nullable=False)
    public_fact_id: Mapped[str] = mapped_column(ForeignKey("public_facts.id"), nullable=False)
    comparable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    conditions: Mapped[list] = mapped_column(JSON, nullable=False)
    missing_fields: Mapped[list] = mapped_column(JSON, default=list)
    mismatch_reasons: Mapped[list] = mapped_column(JSON, default=list)


class VerdictRecord(Base):
    """AI 분석 결과. 담당자 조치와 분리 저장하며 읽기 전용으로 취급한다."""

    __tablename__ = "verdicts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id"), nullable=False)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"), nullable=False)
    public_fact_id: Mapped[str] = mapped_column(ForeignKey("public_facts.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    match_type: Mapped[str | None] = mapped_column(String, nullable=True)
    claim_raw_value: Mapped[str | None] = mapped_column(Numeric, nullable=True)
    public_raw_value: Mapped[str | None] = mapped_column(Numeric, nullable=True)
    claim_normalized_value: Mapped[str | None] = mapped_column(Numeric, nullable=True)
    public_normalized_value: Mapped[str | None] = mapped_column(Numeric, nullable=True)
    absolute_difference: Mapped[str | None] = mapped_column(Numeric, nullable=True)
    relative_difference_pct: Mapped[str | None] = mapped_column(Numeric, nullable=True)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    review_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    review_reasons: Mapped[list] = mapped_column(JSON, default=list)
    follow_up_question: Mapped[str | None] = mapped_column(Text, nullable=True)


class TargetProgressRecord(Base):
    __tablename__ = "target_progress"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id"), nullable=False)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"), nullable=False)
    readiness: Mapped[str] = mapped_column(String, nullable=False)
    baseline_value: Mapped[str | None] = mapped_column(Numeric, nullable=True)
    current_value: Mapped[str | None] = mapped_column(Numeric, nullable=True)
    actual_reduction_pct: Mapped[str | None] = mapped_column(Numeric, nullable=True)
    published_annual_path: Mapped[list | None] = mapped_column(JSON, nullable=True)
    plan_gap: Mapped[str | None] = mapped_column(Numeric, nullable=True)
    on_track: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


class MonitoringCaseRecord(Base):
    __tablename__ = "monitoring_cases"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), nullable=False)
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id"), nullable=False)
    case_type: Mapped[str] = mapped_column(String, nullable=False)
    next_review_date: Mapped[str] = mapped_column(String, nullable=False)
    importance: Mapped[str] = mapped_column(String, nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AnalysisRunRecord(Base):
    """오케스트레이터 한 번의 실행. run lock과 트레이스가 이 id를 기준으로 묶인다."""

    __tablename__ = "analysis_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    monitoring_case_id: Mapped[str] = mapped_column(
        ForeignKey("monitoring_cases.id"), nullable=False
    )
    state: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TraceEventRecord(Base):
    __tablename__ = "trace_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id"), nullable=False)
    step_type: Mapped[str] = mapped_column(String, nullable=False)
    stage: Mapped[str] = mapped_column(String, nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String, nullable=True)
    input_summary: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class HumanReviewRecord(Base):
    """담당자 조치. append-only 이력이며 AI Verdict를 덮어쓰지 않는다."""

    __tablename__ = "human_reviews"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("monitoring_cases.id"), nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    reviewer: Mapped[str] = mapped_column(String, nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    previous_action: Mapped[str | None] = mapped_column(String, nullable=True)
