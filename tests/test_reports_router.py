import hashlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app
from api.routers import reports as reports_module
from db.models import Base
from db.session import get_session

REFERENCES = Path(__file__).parents[1] / "references"


@pytest.fixture
def session_factory() -> Iterator[sessionmaker[Session]]:
    """요청마다 격리된 인메모리 SQLite — 전역 db/session.py 싱글턴을 건드리지 않는다."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    yield factory
    engine.dispose()


@pytest.fixture
def client(session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    def override_get_session() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _file_hash(filename: str) -> str:
    digest = hashlib.sha256()
    with (REFERENCES / filename).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _seed_report(
    session_factory: sessionmaker[Session],
    *,
    report_id: str,
    file_hash: str,
) -> None:
    from db.models import Company, Report as ReportRecord

    session = session_factory()
    try:
        session.add(Company(id="company-x", legal_name="테스트 기업"))
        session.add(
            ReportRecord(
                id=report_id,
                company_id="company-x",
                title="테스트 보고서",
                reporting_year=2024,
                file_hash=file_hash,
                source_url="https://example.com/report.pdf",
            )
        )
        session.commit()
    finally:
        session.close()


def _seed_claim(
    session_factory: sessionmaker[Session],
    *,
    claim_id: str,
    report_id: str,
    page: int,
    value: str,
) -> None:
    from db.models import Claim as ClaimRecord

    session = session_factory()
    try:
        session.add(
            ClaimRecord(
                id=claim_id,
                report_id=report_id,
                claim_type="실적주장",
                metric="온실가스 배출량",
                value=value,
                unit="tCO2eq",
                value_basis="절대량",
                period_start="2024-01-01",
                period_end="2024-12-31",
                scope="Scope 1",
                organization_boundary="별도",
                geographic_boundary="대한민국 국내 사업장",
                entity_level="기업",
                raw_text="테스트 원문",
                page=page,
                evidence="테스트 근거",
                confidence=1.0,
                extraction_mode="verified_cache",
            )
        )
        session.commit()
    finally:
        session.close()


@pytest.mark.skipif(
    not (REFERENCES / "Samsung-Biologics-2025-ESG-Report_KR.pdf").is_file(),
    reason="원본 PDF fixture가 저장소에 없습니다",
)
def test_get_pdf_returns_file_for_mapped_report(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    _seed_report(
        session_factory,
        report_id="report-a-2024",
        file_hash=_file_hash("Samsung-Biologics-2025-ESG-Report_KR.pdf"),
    )
    response = client.get("/reports/report-a-2024/pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content[:4] == b"%PDF"


@pytest.mark.skipif(
    not (REFERENCES / "Samsung_Electronics_Sustainability_Report_2025_ENG.pdf").is_file(),
    reason="원본 PDF fixture가 저장소에 없습니다",
)
def test_get_pdf_supports_range_requests(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    _seed_report(
        session_factory,
        report_id="report-b-2024",
        file_hash=_file_hash("Samsung_Electronics_Sustainability_Report_2025_ENG.pdf"),
    )
    response = client.get(
        "/reports/report-b-2024/pdf", headers={"Range": "bytes=0-1023"}
    )
    assert response.status_code == 206
    assert response.headers["content-range"].startswith("bytes 0-1023/")
    assert len(response.content) == 1024


def test_get_pdf_for_synthetic_report_is_404(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    _seed_report(
        session_factory,
        report_id="report-c-2024",
        file_hash="synthetic-report-fixture",
    )
    response = client.get("/reports/report-c-2024/pdf")
    assert response.status_code == 404


def test_get_pdf_for_unknown_report_id_is_404(client: TestClient) -> None:
    response = client.get("/reports/nonexistent/pdf")
    assert response.status_code == 404


def test_pdf_meta_reports_unavailable_for_synthetic_report(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    _seed_report(
        session_factory,
        report_id="report-c-2024",
        file_hash="synthetic-report-fixture",
    )
    response = client.get("/reports/report-c-2024/pdf/meta")
    assert response.status_code == 200
    assert response.json() == {"available": False}


@pytest.mark.skipif(
    not (REFERENCES / "Samsung-Biologics-2025-ESG-Report_KR.pdf").is_file(),
    reason="원본 PDF fixture가 저장소에 없습니다",
)
def test_pdf_meta_reports_available_for_mapped_report(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    _seed_report(
        session_factory,
        report_id="report-a-2024",
        file_hash=_file_hash("Samsung-Biologics-2025-ESG-Report_KR.pdf"),
    )
    response = client.get("/reports/report-a-2024/pdf/meta")
    assert response.status_code == 200
    assert response.json() == {
        "available": True,
        "filename": "Samsung-Biologics-2025-ESG-Report_KR.pdf",
    }


@pytest.mark.skipif(
    not (REFERENCES / "Samsung-Biologics-2025-ESG-Report_KR.pdf").is_file(),
    reason="원본 PDF fixture가 저장소에 없습니다",
)
def test_get_pdf_rejects_file_hash_mismatch(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    """매핑 테이블은 맞지만 Report.file_hash가 실제 파일과 다르면 서빙을 중단한다."""
    _seed_report(
        session_factory,
        report_id="report-a-2024",
        file_hash="sha256:" + "0" * 64,
    )
    response = client.get("/reports/report-a-2024/pdf")
    assert response.status_code == 500


def test_report_id_to_filename_mapping_has_no_entry_for_synthetic_case() -> None:
    assert "report-c-2024" not in reports_module.REPORT_ID_TO_FILENAME


@pytest.mark.skipif(
    not (REFERENCES / "Samsung-Biologics-2025-ESG-Report_KR.pdf").is_file(),
    reason="원본 PDF fixture가 저장소에 없습니다",
)
def test_pdf_highlight_finds_bbox_for_known_value(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    _seed_report(
        session_factory,
        report_id="report-a-2024",
        file_hash=_file_hash("Samsung-Biologics-2025-ESG-Report_KR.pdf"),
    )
    _seed_claim(
        session_factory,
        claim_id="claim-a-scope1",
        report_id="report-a-2024",
        page=171,
        value="71840.290",
    )
    response = client.get(
        "/reports/report-a-2024/pdf/highlight",
        params={"claim_id": "claim-a-scope1"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["found"] is True
    assert body["page"] == 171
    assert body["x1"] > body["x0"]
    assert body["bottom"] > body["top"]
    assert body["page_width"] > 0
    assert body["page_height"] > 0


@pytest.mark.skipif(
    not (REFERENCES / "Samsung-Biologics-2025-ESG-Report_KR.pdf").is_file(),
    reason="원본 PDF fixture가 저장소에 없습니다",
)
def test_pdf_highlight_returns_not_found_for_absent_value(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    _seed_report(
        session_factory,
        report_id="report-a-2024",
        file_hash=_file_hash("Samsung-Biologics-2025-ESG-Report_KR.pdf"),
    )
    _seed_claim(
        session_factory,
        claim_id="claim-a-nonexistent",
        report_id="report-a-2024",
        page=171,
        value="999999999",
    )
    response = client.get(
        "/reports/report-a-2024/pdf/highlight",
        params={"claim_id": "claim-a-nonexistent"},
    )
    assert response.status_code == 200
    assert response.json() == {"found": False}


def test_pdf_highlight_rejects_claim_from_other_report(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    _seed_report(
        session_factory,
        report_id="report-c-2024",
        file_hash="synthetic-report-fixture",
    )
    _seed_claim(
        session_factory,
        claim_id="claim-other-report",
        report_id="some-other-report",
        page=1,
        value="100",
    )
    response = client.get(
        "/reports/report-c-2024/pdf/highlight",
        params={"claim_id": "claim-other-report"},
    )
    # report-c-2024는 실물 PDF가 없어 _resolve_pdf_path에서 먼저 404가 난다.
    assert response.status_code == 404


def test_pdf_highlight_unknown_claim_is_404(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    _seed_report(
        session_factory,
        report_id="report-c-2024",
        file_hash="synthetic-report-fixture",
    )
    response = client.get(
        "/reports/report-c-2024/pdf/highlight",
        params={"claim_id": "nonexistent-claim"},
    )
    assert response.status_code == 404
