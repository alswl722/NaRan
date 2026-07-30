"""테이블 생성과 A·B·C 검증 fixture 적재.

`python -m db.init_db`로 실행한다. fixture는 naran/contracts.py의 Pydantic
계약으로 먼저 검증한 뒤 ORM 모델로 옮겨, 잘못된 값이 DB에 들어가지 않게
한다. 이미 적재된 레코드는 건드리지 않아 재실행해도 안전하다(idempotent).
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from db.models import (
    Base,
    Claim as ClaimRecord,
    Company as CompanyRecord,
    MonitoringCaseRecord,
    PublicFact as PublicFactRecord,
    Report as ReportRecord,
)
from db.session import get_engine, get_session
from naran.contracts import (
    Claim,
    Company,
    MonitoringCase,
    PublicFact,
    Report,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
CASE_FILES = ("sample_case_a.json", "sample_case_b.json", "sample_case_c.json")


def create_all_tables() -> None:
    Base.metadata.create_all(get_engine())


def _load_case(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _upsert_company(session: Session, company: Company) -> None:
    if session.get(CompanyRecord, company.id) is not None:
        return
    session.add(
        CompanyRecord(
            id=company.id,
            legal_name=company.legal_name,
            identifiers=company.identifiers,
            aliases=company.aliases,
        )
    )


def _upsert_report(session: Session, report: Report) -> None:
    if session.get(ReportRecord, report.id) is not None:
        return
    session.add(
        ReportRecord(
            id=report.id,
            company_id=report.company_id,
            title=report.title,
            reporting_year=report.reporting_year,
            file_hash=report.file_hash,
            source_url=report.source_url,
        )
    )


def _upsert_claim(session: Session, claim: Claim) -> None:
    if session.get(ClaimRecord, claim.id) is not None:
        return
    session.add(
        ClaimRecord(
            id=claim.id,
            report_id=claim.report_id,
            claim_type=claim.claim_type.value,
            metric=claim.metric,
            value=claim.value,
            unit=claim.unit,
            value_basis=claim.value_basis.value if claim.value_basis else None,
            period_start=claim.period_start,
            period_end=claim.period_end,
            baseline_year=claim.baseline_year,
            target_year=claim.target_year,
            scope=claim.scope.value if claim.scope else None,
            scope2_method=claim.scope2_method.value if claim.scope2_method else None,
            organization_boundary=(
                claim.organization_boundary.value if claim.organization_boundary else None
            ),
            geographic_boundary=claim.geographic_boundary,
            entity_level=claim.entity_level.value if claim.entity_level else None,
            raw_text=claim.raw_text,
            page=claim.page,
            evidence=claim.evidence,
            confidence=claim.confidence,
            extraction_mode=claim.extraction_mode.value,
        )
    )


def _upsert_public_fact(session: Session, fact: PublicFact) -> None:
    if session.get(PublicFactRecord, fact.id) is not None:
        return
    session.add(
        PublicFactRecord(
            id=fact.id,
            company_id=fact.company_id,
            site_id=fact.site_id,
            entity_level=fact.entity_level.value,
            metric=fact.metric,
            raw_value=fact.raw_value,
            normalized_value=fact.normalized_value,
            unit=fact.unit,
            value_basis=fact.value_basis.value if fact.value_basis else None,
            period_start=fact.period_start,
            period_end=fact.period_end,
            scope=fact.scope.value if fact.scope else None,
            scope2_method=fact.scope2_method.value if fact.scope2_method else None,
            organization_boundary=(
                fact.organization_boundary.value if fact.organization_boundary else None
            ),
            geographic_boundary=fact.geographic_boundary,
            display_decimal_places=fact.display_decimal_places,
            display_rule=fact.display_rule,
            disclosure_duty=fact.disclosure_duty.value,
            source_url=fact.source_url,
            retrieved_at=fact.retrieved_at,
            source_hash=fact.source_hash,
            version=fact.version,
        )
    )


def _upsert_monitoring_case(session: Session, case: MonitoringCase) -> None:
    if session.get(MonitoringCaseRecord, case.id) is not None:
        return
    session.add(
        MonitoringCaseRecord(
            id=case.id,
            company_id=case.company_id,
            report_id=case.report_id,
            case_type=case.case_type,
            next_review_date=case.next_review_date,
            importance=case.importance,
            monitoring_data_synthetic=case.monitoring_data_synthetic,
        )
    )


def load_fixture_case(session: Session, case_data: dict) -> None:
    """계약 검증을 통과한 fixture 하나를 DB에 적재한다."""

    company = Company.model_validate(case_data["company"])
    report = Report.model_validate(case_data["report"])
    monitoring_case = MonitoringCase.model_validate(case_data["monitoring_case"])
    claims = [Claim.model_validate(c) for c in case_data["claims"]]
    public_facts = [PublicFact.model_validate(f) for f in case_data["public_facts"]]

    _upsert_company(session, company)
    _upsert_report(session, report)
    for claim in claims:
        _upsert_claim(session, claim)
    for fact in public_facts:
        _upsert_public_fact(session, fact)
    _upsert_monitoring_case(session, monitoring_case)


def seed_verified_cases(session: Session) -> None:
    for filename in CASE_FILES:
        case_data = _load_case(FIXTURES_DIR / filename)
        load_fixture_case(session, case_data)
    session.commit()


def main() -> None:
    create_all_tables()
    session = next(get_session())
    try:
        seed_verified_cases(session)
    finally:
        session.close()


if __name__ == "__main__":
    main()
