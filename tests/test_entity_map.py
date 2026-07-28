import pytest

from db.entity_map import (
    BoundaryCoverage,
    DEFAULT_ENTITY_MAP,
    EntityMap,
    EntityMapping,
    MappingStatus,
    SourceSystem,
)


def test_case_a_explicit_mapping_can_align_2024_boundary() -> None:
    assert DEFAULT_ENTITY_MAP.permits_boundary_alignment(
        source_system=SourceSystem.ENV_INFO,
        source_entity_id="CT000000000000002772",
        company_id="company-samsung-biologics",
        year=2024,
    )


def test_case_a_mapping_does_not_leak_to_another_year() -> None:
    assert not DEFAULT_ENTITY_MAP.permits_boundary_alignment(
        source_system=SourceSystem.ENV_INFO,
        source_entity_id="CT000000000000002772",
        company_id="company-samsung-biologics",
        year=2025,
    )


def test_case_b_site_is_known_but_cannot_replace_global_boundary() -> None:
    mapping = DEFAULT_ENTITY_MAP.find(
        source_system=SourceSystem.ENV_INFO,
        source_entity_id="00000000000000095329",
        company_id="company-samsung-electronics",
        year=2024,
    )

    assert mapping is not None
    assert mapping.boundary_coverage is BoundaryCoverage.SUBSET
    assert not mapping.permits_boundary_alignment(2024)


def test_similar_name_is_not_used_as_mapping_evidence() -> None:
    assert DEFAULT_ENTITY_MAP.find(
        source_system=SourceSystem.ENV_INFO,
        source_entity_id="unknown-site-id",
        company_id="company-samsung-electronics",
        year=2024,
    ) is None


def test_unreviewed_mapping_cannot_align_boundary() -> None:
    entity_map = EntityMap(
        [
            EntityMapping(
                source_system=SourceSystem.ENV_INFO,
                source_entity_id="candidate-site",
                company_id="candidate-company",
                source_entity_name="유사한 기업명",
                status=MappingStatus.REQUIRES_REVIEW,
                boundary_coverage=BoundaryCoverage.EXACT,
                valid_from_year=2024,
                valid_to_year=None,
                evidence=("이름 후보만 확인",),
                note="수동 검토 필요",
            )
        ]
    )

    assert not entity_map.permits_boundary_alignment(
        source_system=SourceSystem.ENV_INFO,
        source_entity_id="candidate-site",
        company_id="candidate-company",
        year=2024,
    )


def test_overlapping_mapping_records_are_rejected_at_lookup() -> None:
    duplicate = EntityMapping(
        source_system=SourceSystem.ENV_INFO,
        source_entity_id="duplicate-site",
        company_id="duplicate-company",
        source_entity_name="중복 사업장",
        status=MappingStatus.VERIFIED,
        boundary_coverage=BoundaryCoverage.EXACT,
        valid_from_year=2024,
        valid_to_year=2024,
        evidence=("명시적 식별자 확인",),
        note="테스트",
    )
    with pytest.raises(ValueError, match="중복"):
        EntityMap([duplicate, duplicate])
