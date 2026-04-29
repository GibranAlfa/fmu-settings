"""Tests for mapping models."""

from typing import Literal

import pytest
from fmu.datamodels.context.mappings import DataSystem, MappingType, RelationType
from pydantic import ValidationError

from fmu.settings.models.mappings import MappableIdentifierMapping, MappableMappings


def _mappable_mapping(
    source_id: str = "TopVolantis",
    target_id: str = "VOLANTIS GP. Top",
    relation_type: Literal[
        RelationType.primary, RelationType.alias
    ] = RelationType.primary,
) -> MappableIdentifierMapping:
    return MappableIdentifierMapping(
        source_system=DataSystem.rms,
        target_system=DataSystem.smda,
        mapping_type=MappingType.stratigraphy,
        relation_type=relation_type,
        source_id=source_id,
        target_id=target_id,
    )


def test_mappable_mappings_behaves_like_sequence() -> None:
    """MappableMappings exposes simple list-like access."""
    primary = _mappable_mapping()
    alias = _mappable_mapping("TopVOLANTIS", relation_type=RelationType.alias)

    mappings = MappableMappings(root=[primary, alias])

    expected_mapping_count = 2
    assert len(mappings) == expected_mapping_count
    assert mappings[0] == primary
    assert list(mappings) == [primary, alias]


def test_mappable_mappings_serializes_to_json_list() -> None:
    """MappableMappings serializes as a root list."""
    mappings = MappableMappings(root=[_mappable_mapping()])

    assert mappings.model_dump(mode="json", exclude_none=True) == [
        {
            "source_system": "rms",
            "target_system": "smda",
            "mapping_type": "stratigraphy",
            "relation_type": "primary",
            "source_id": "TopVolantis",
            "target_id": "VOLANTIS GP. Top",
        }
    ]


def test_mappable_identifier_mapping_rejects_same_system_mapping() -> None:
    """Mappable mappings must point from one system to another."""
    with pytest.raises(ValidationError, match="cross-system mappings"):
        MappableIdentifierMapping(
            source_system=DataSystem.rms,
            target_system=DataSystem.rms,
            mapping_type=MappingType.stratigraphy,
            relation_type=RelationType.primary,
            source_id="TopVolantis",
            target_id="TopVolantis",
        )


def test_mappable_identifier_mapping_rejects_unmappable_relation() -> None:
    """Mappable mappings cannot contain unmappable relations."""
    with pytest.raises(ValidationError):
        MappableIdentifierMapping(
            source_system=DataSystem.rms,
            target_system=DataSystem.smda,
            mapping_type=MappingType.stratigraphy,
            relation_type=RelationType.unmappable,  # type: ignore[arg-type]
            source_id="TopVolantis",
            target_id="VOLANTIS GP. Top",
        )


def test_mappable_identifier_mapping_rejects_empty_identifiers() -> None:
    """Source and target identifiers must not be empty."""
    with pytest.raises(ValidationError, match="identifier cannot be an empty string"):
        _mappable_mapping(source_id=" ")

    with pytest.raises(ValidationError, match="identifier cannot be an empty string"):
        _mappable_mapping(target_id=" ")
