"""법인과 공개 데이터 사업장 식별자의 명시적 매핑.

기업명 유사도나 배출량 숫자 일치만으로 매핑을 만들지 않는다. 비교에 사용할
수 있는 범위 정렬은 출처 식별자, 적용 기간, 검증 상태와 범위 관계가 모두
명시된 레코드로만 허용한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable


class MappingStatus(StrEnum):
    VERIFIED = "verified"
    REQUIRES_REVIEW = "requires_review"
    REJECTED = "rejected"


class SourceSystem(StrEnum):
    ENV_INFO = "env-info"
    GIR = "gir"


class BoundaryCoverage(StrEnum):
    EXACT = "exact"
    SUBSET = "subset"
    SUPERSET = "superset"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class EntityMapping:
    source_system: SourceSystem
    source_entity_id: str
    company_id: str
    source_entity_name: str
    status: MappingStatus
    boundary_coverage: BoundaryCoverage
    valid_from_year: int
    valid_to_year: int | None
    evidence: tuple[str, ...]
    note: str

    def applies_to(self, year: int) -> bool:
        return (
            year >= self.valid_from_year
            and (self.valid_to_year is None or year <= self.valid_to_year)
        )

    def permits_boundary_alignment(self, year: int) -> bool:
        return (
            self.applies_to(year)
            and self.status is MappingStatus.VERIFIED
            and self.boundary_coverage is BoundaryCoverage.EXACT
            and bool(self.evidence)
        )


class EntityMap:
    def __init__(self, mappings: Iterable[EntityMapping] = ()) -> None:
        self._mappings = tuple(mappings)
        self._validate_non_overlapping_periods()

    def _validate_non_overlapping_periods(self) -> None:
        for index, left in enumerate(self._mappings):
            for right in self._mappings[index + 1 :]:
                same_key = (
                    left.source_system == right.source_system
                    and left.source_entity_id == right.source_entity_id
                    and left.company_id == right.company_id
                )
                left_end = left.valid_to_year if left.valid_to_year is not None else 9999
                right_end = right.valid_to_year if right.valid_to_year is not None else 9999
                overlaps = (
                    left.valid_from_year <= right_end
                    and right.valid_from_year <= left_end
                )
                if same_key and overlaps:
                    raise ValueError("같은 기간에 중복되는 기업·사업장 매핑이 있습니다")

    def find(
        self,
        *,
        source_system: SourceSystem,
        source_entity_id: str,
        company_id: str,
        year: int,
    ) -> EntityMapping | None:
        matches = [
            mapping
            for mapping in self._mappings
            if mapping.source_system == source_system
            and mapping.source_entity_id == source_entity_id
            and mapping.company_id == company_id
            and mapping.applies_to(year)
        ]
        return matches[0] if matches else None

    def permits_boundary_alignment(
        self,
        *,
        source_system: SourceSystem,
        source_entity_id: str,
        company_id: str,
        year: int,
    ) -> bool:
        mapping = self.find(
            source_system=source_system,
            source_entity_id=source_entity_id,
            company_id=company_id,
            year=year,
        )
        return mapping is not None and mapping.permits_boundary_alignment(year)


DEFAULT_ENTITY_MAP = EntityMap(
    [
        EntityMapping(
            source_system=SourceSystem.ENV_INFO,
            source_entity_id="CT000000000000002772",
            company_id="company-samsung-biologics",
            source_entity_name="삼성바이오로직스(주) 1단지",
            status=MappingStatus.VERIFIED,
            boundary_coverage=BoundaryCoverage.EXACT,
            valid_from_year=2024,
            valid_to_year=2024,
            evidence=(
                "환경정보공개시스템 2024 대표사업장 레코드는 Scope 1을 기업 경계 내 배출량으로 명시",
                "환경정보공개시스템 레코드는 해당 사업장을 삼성바이오로직스의 대표사업장으로 명시",
                "삼성바이오로직스 2025 ESG 보고서는 2024년 국내 사업장 별도 범위를 명시",
            ),
            note=(
                "2024년에 한해 보고서의 삼성바이오로직스 별도 국내 사업장 "
                "온실가스 범위와 정렬된 검증 매핑"
            ),
        ),
        EntityMapping(
            source_system=SourceSystem.GIR,
            source_entity_id="gir-samsung-biologics-2024",
            company_id="company-samsung-biologics",
            source_entity_name="삼성바이오로직스 주식회사",
            status=MappingStatus.VERIFIED,
            boundary_coverage=BoundaryCoverage.EXACT,
            valid_from_year=2024,
            valid_to_year=2024,
            evidence=(
                "GIR 2024 명세서 통계는 법인명을 삼성바이오로직스 주식회사로 명시",
                "GIR 총량 226,519tCO2eq가 보고서 p.220 검증 총량과 일치",
                "GIR과 보고서 검증보고서의 검증수행기관이 대일이엔씨기술㈜로 일치",
            ),
            note=(
                "2024년 GIR 명세서 총량과 보고서 검증 범위의 법인·기간·"
                "검증기관을 함께 확인한 명시적 매핑"
            ),
        ),
        EntityMapping(
            source_system=SourceSystem.ENV_INFO,
            source_entity_id="00000000000000095329",
            company_id="company-samsung-electronics",
            source_entity_name="삼성전자(주) 수원사업장",
            status=MappingStatus.VERIFIED,
            boundary_coverage=BoundaryCoverage.SUBSET,
            valid_from_year=2024,
            valid_to_year=2024,
            evidence=(
                "환경정보공개시스템 2024 사업장명이 삼성전자(주) 수원사업장으로 명시",
                "삼성전자 2025 지속가능경영보고서 p.68은 한국·해외 제조 자회사 범위",
            ),
            note="법인 소속은 확인됐지만 글로벌 제조 자회사 보고 범위의 일부이므로 직접 비교 금지",
        ),
    ]
)
