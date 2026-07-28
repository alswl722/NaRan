from datetime import datetime
from decimal import Decimal

import pytest

from db.envinfo import EnvRecord, parse
from db.public_data import (
    GirRecord,
    PublicDataContext,
    normalize_envinfo,
    normalize_gir,
    response_hash,
)
from naran.contracts import (
    DisclosureDuty,
    EntityLevel,
    OrganizationBoundary,
    Scope,
    Scope2Method,
)


def context(
    *,
    site_id: str = "SITE-1",
    source_url: str = "https://env-info.kr/example",
    duty: DisclosureDuty = DisclosureDuty.VOLUNTARY,
) -> PublicDataContext:
    return PublicDataContext(
        company_id="company-1",
        site_id=site_id,
        entity_level=EntityLevel.BUSINESS_SITE,
        organization_boundary=OrganizationBoundary.BUSINESS_SITE,
        geographic_boundary="대한민국 국내 사업장",
        scope2_method=Scope2Method.ETS,
        disclosure_duty=duty,
        source_url=source_url,
        retrieved_at=datetime.fromisoformat("2026-07-28T00:00:00+09:00"),
        source_hash="sha256:" + "a" * 64,
        version="2024-retrieved-2026-07-28",
        display_decimal_places=0,
        display_rule=None,
    )


def test_envinfo_parser_preserves_legitimate_zero() -> None:
    html = """
    사업장명 시험사업장 대표자 홍길동
    직접배출량(scopeⅠ) 0 ton CO2 eq
    간접배출량(scopeⅡ) 0 ton CO2 eq
    온실가스배출총량 0 ton CO2 eq
    """

    record = parse(html, "SITE-1", 2024)

    assert record.scope1_tco2e == Decimal("0")
    assert record.scope2_tco2e == Decimal("0")
    assert record.scope12_tco2e == Decimal("0")
    assert record.missing_reason is None


def test_envinfo_parser_only_converts_zero_with_explicit_missing_marker() -> None:
    html = """
    사업장명 시험사업장 대표자 홍길동
    직접배출량(scopeⅠ) 0 ton CO2 eq
    간접배출량(scopeⅡ) 0 ton CO2 eq
    온실가스배출총량 0 ton CO2 eq
    전년도 입력 정보 없음
    """

    record = parse(html, "SITE-1", 2024)

    assert record.scope1_tco2e is None
    assert record.scope2_tco2e is None
    assert record.scope12_tco2e is None
    assert record.missing_reason


def test_envinfo_does_not_treat_reported_total_as_scope12() -> None:
    html = "온실가스배출총량 100 ton CO2 eq"

    record = parse(html, "SITE-1", 2024)

    assert record.reported_total_tco2e == Decimal("100")
    assert record.scope12_tco2e is None


def test_envinfo_normalization_preserves_metadata_and_missing_value() -> None:
    record = EnvRecord(
        comp_id="SITE-1",
        year=2024,
        scope1_tco2e=Decimal("10"),
        scope2_tco2e=None,
        scope12_tco2e=None,
    )

    facts = normalize_envinfo(record, context=context())
    by_scope = {fact.scope: fact for fact in facts}

    assert by_scope[Scope.SCOPE_1].raw_value == Decimal("10")
    assert by_scope[Scope.SCOPE_2].raw_value is None
    assert by_scope[Scope.SCOPE_2].normalized_value is None
    assert by_scope[Scope.SCOPE_2].disclosure_duty is DisclosureDuty.VOLUNTARY
    assert by_scope[Scope.SCOPE_2].source_hash == "sha256:" + "a" * 64
    assert by_scope[Scope.SCOPE_2].version == "2024-retrieved-2026-07-28"


def test_gir_normalization_is_mandatory_scope12() -> None:
    record = GirRecord(
        entity_id="GIR-1",
        year=2024,
        emissions_tco2eq=Decimal("226519"),
    )
    gir_context = context(
        site_id="GIR-1",
        source_url="https://gir.go.kr/example",
        duty=DisclosureDuty.MANDATORY,
    )

    fact = normalize_gir(record, context=gir_context)

    assert fact.scope is Scope.SCOPE_1_2
    assert fact.raw_value == Decimal("226519")
    assert fact.scope2_method is Scope2Method.ETS
    assert fact.disclosure_duty is DisclosureDuty.MANDATORY


def test_response_hash_is_stable_and_source_sensitive() -> None:
    assert response_hash(b"same") == response_hash(b"same")
    assert response_hash(b"same") != response_hash(b"different")


def test_unrelated_missing_text_does_not_turn_zero_into_null() -> None:
    html = """
    직접배출량(scopeⅠ) 0 ton CO2 eq
    간접배출량(scopeⅡ) 0 ton CO2 eq
    온실가스배출총량 0 ton CO2 eq
    환경법규 위반 내역 미공개
    """

    record = parse(html, "SITE-1", 2024)

    assert record.scope1_tco2e == Decimal("0")
    assert record.scope2_tco2e == Decimal("0")


def test_spoofed_envinfo_hostname_is_rejected() -> None:
    record = EnvRecord(comp_id="SITE-1", year=2024)
    spoofed = context(source_url="https://evil-env-info.kr/example")

    with pytest.raises(ValueError, match="env-info 출처"):
        normalize_envinfo(record, context=spoofed)


@pytest.mark.parametrize("invalid", [Decimal("-1"), Decimal("NaN")])
def test_invalid_public_emission_value_is_rejected(invalid: Decimal) -> None:
    record = EnvRecord(
        comp_id="SITE-1",
        year=2024,
        scope1_tco2e=invalid,
    )

    with pytest.raises(ValueError, match="유한한 0 이상"):
        normalize_envinfo(record, context=context())


def test_invalid_source_hash_is_rejected() -> None:
    data = context().model_dump()
    data["source_hash"] = "sha256:bad"

    with pytest.raises(ValueError, match="source_hash"):
        PublicDataContext.model_validate(data)
