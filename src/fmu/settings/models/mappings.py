"""Model for the mappings.json file."""

from collections.abc import Iterator
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, RootModel, field_validator, model_validator

from fmu.datamodels.context.mappings import (
    DataSystem,
    MappingType,
    RelationType,
    StratigraphyMappings,
    WellboreMappings,
)


class Mappings(BaseModel):
    """Represents the mappings file in a .fmu directory."""

    stratigraphy: StratigraphyMappings = Field(
        default_factory=lambda: StratigraphyMappings(root=[])
    )
    """Stratigraphy mappings in the mappings file."""

    wellbore: WellboreMappings = Field(
        default_factory=lambda: WellboreMappings(root=[])
    )
    """Wellbore mappings in the mappings file."""


class MappableIdentifierMapping(BaseModel):
    """Identifier mapping that can be used as a mappable mapping."""

    source_system: DataSystem
    target_system: DataSystem
    mapping_type: MappingType
    relation_type: Literal[RelationType.primary, RelationType.alias]
    source_id: str
    source_uuid: UUID | None = None
    target_id: str
    target_uuid: UUID | None = None

    @field_validator("source_id", "target_id")
    @classmethod
    def validate_identifier_not_empty(cls, value: str) -> str:
        """Ensure identifiers are not empty strings."""
        if not value or not value.strip():
            raise ValueError("An identifier cannot be an empty string")
        return value.strip()

    @model_validator(mode="after")
    def validate_cross_system_mapping(self: Self) -> Self:
        """Ensure mappable mappings only contain cross-system mappings."""
        if self.source_system == self.target_system:
            raise ValueError("Mappable mappings must be cross-system mappings")
        return self


class MappableMappings(RootModel[list[MappableIdentifierMapping]]):
    """Mappings containing only entries that can map to another system."""

    root: list[MappableIdentifierMapping]

    def __getitem__(self: Self, index: int) -> MappableIdentifierMapping:
        """Retrieve a mappable mapping from the list by index."""
        return self.root[index]

    def __iter__(self: Self) -> Iterator[MappableIdentifierMapping]:  # type: ignore[override]
        """Return an iterator for the mappable mappings."""
        return iter(self.root)

    def __len__(self: Self) -> int:
        """Return the number of mappable mappings."""
        return len(self.root)
