"""출처별 공개 레코드를 공통 PublicFact로 정규화한다."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from urllib.parse import urlparse

from db.envinfo import EnvRecord
from naran.contracts import (
    ContractModel,
    DisclosureDuty,
    EntityLevel,
    OrganizationBoundary,
    PublicFact,
    Scope,
    Scope2Method,
    ValueBasis,
)


class PublicDataContext(ContractModel):
    company_id: str
    site_id: str | None
    entity_level: EntityLevel
    organization_boundary: OrganizationBoundary
    geographic_boundary: str
    scope2_method: Scope2Method | None
    disclosure_duty: DisclosureDuty
    source_url: str
    retrieved_at: datetime
    source_hash: str
    version: str
    display_decimal_places: int | None
    display_rule: str | None

    def validate_provenance(self) -> None:
        if not all(
            value.strip()
            for value in (
                self.company_id,
                self.geographic_boundary,
                self.source_url,
                self.source_hash,
                self.version,
            )
        ):
            raise ValueError("공개 데이터 provenance 필드는 공백일 수 없습니다")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", self.source_hash):
            raise ValueError("source_hash는 sha256:<64자리 소문자 hex> 형식이어야 합니다")
        if self.retrieved_at.tzinfo is None:
            raise ValueError("retrieved_at에는 시간대가 필요합니다")


@dataclass(frozen=True)
class GirRecord:
    entity_id: str
    year: int
    emissions_tco2eq: Decimal | None


def response_hash(raw_response: bytes) -> str:
    return f"sha256:{hashlib.sha256(raw_response).hexdigest()}"


def _is_official_host(url: str, host: str) -> bool:
    hostname = urlparse(url).hostname
    return hostname == host or hostname == f"www.{host}"


def _fact_id(
    *,
    source: str,
    company_id: str,
    site_id: str | None,
    year: int,
    scope: Scope,
    version: str,
) -> str:
    raw = "|".join(
        (source, company_id, site_id or "", str(year), scope.value, version)
    )
    return f"fact-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"


def _fact(
    *,
    source: str,
    year: int,
    scope: Scope,
    value: Decimal | None,
    context: PublicDataContext,
) -> PublicFact:
    context.validate_provenance()
    if value is not None and (not value.is_finite() or value < 0):
        raise ValueError("공개 배출량은 유한한 0 이상의 값이어야 합니다")
    return PublicFact(
        id=_fact_id(
            source=source,
            company_id=context.company_id,
            site_id=context.site_id,
            year=year,
            scope=scope,
            version=context.version,
        ),
        company_id=context.company_id,
        site_id=context.site_id,
        entity_level=context.entity_level,
        metric="온실가스 배출량",
        raw_value=value,
        normalized_value=value,
        unit="tCO2eq",
        value_basis=ValueBasis.ABSOLUTE,
        period_start=f"{year}-01-01",
        period_end=f"{year}-12-31",
        scope=scope,
        scope2_method=(
            context.scope2_method
            if scope in {Scope.SCOPE_2, Scope.SCOPE_1_2}
            else None
        ),
        organization_boundary=context.organization_boundary,
        geographic_boundary=context.geographic_boundary,
        display_decimal_places=context.display_decimal_places,
        display_rule=context.display_rule,
        disclosure_duty=context.disclosure_duty,
        source_url=context.source_url,
        retrieved_at=context.retrieved_at,
        source_hash=context.source_hash,
        version=context.version,
    )


def normalize_envinfo(
    record: EnvRecord,
    *,
    context: PublicDataContext,
) -> tuple[PublicFact, ...]:
    """env-info 수치를 추론 없이 Scope별 PublicFact로 변환한다."""

    if context.site_id != record.comp_id:
        raise ValueError("context.site_id와 env-info COMP_ID가 일치해야 합니다")
    if not _is_official_host(context.source_url, "env-info.kr"):
        raise ValueError("env-info 정규화에는 env-info 출처 URL이 필요합니다")
    return (
        _fact(
            source="env-info",
            year=record.year,
            scope=Scope.SCOPE_1,
            value=record.scope1_tco2e,
            context=context,
        ),
        _fact(
            source="env-info",
            year=record.year,
            scope=Scope.SCOPE_2,
            value=record.scope2_tco2e,
            context=context,
        ),
        _fact(
            source="env-info",
            year=record.year,
            scope=Scope.SCOPE_1_2,
            value=record.scope12_tco2e,
            context=context,
        ),
    )


def normalize_gir(
    record: GirRecord,
    *,
    context: PublicDataContext,
) -> PublicFact:
    """GIR 명세서 배출량을 Scope 1+2 PublicFact로 변환한다."""

    if context.site_id != record.entity_id:
        raise ValueError("context.site_id와 GIR 엔터티 ID가 일치해야 합니다")
    if not _is_official_host(context.source_url, "gir.go.kr"):
        raise ValueError("GIR 정규화에는 GIR 출처 URL이 필요합니다")
    if context.disclosure_duty is not DisclosureDuty.MANDATORY:
        raise ValueError("GIR 명세서 정규화 공개 성격은 의무여야 합니다")
    return _fact(
        source="gir",
        year=record.year,
        scope=Scope.SCOPE_1_2,
        value=record.emissions_tco2eq,
        context=context,
    )
