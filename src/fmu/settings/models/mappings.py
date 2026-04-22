"""Model for the mappings.json file."""

from typing import Any, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_serializer, model_validator

from fmu.datamodels.context.mappings import (
    AnyIdentifierMapping,
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


class MappingGroup(BaseModel):
    """A mapping group containing related mappings with a shared target context.

    This is a view of the data for GUI display purposes, not how it's stored.
    Groups mappings that share target_id, target_uuid (if set), mapping_type,
    target_system, and source_system.
    """

    target_id: str
    target_uuid: UUID | None = None
    mapping_type: MappingType
    target_system: DataSystem
    source_system: DataSystem
    mappings: list[AnyIdentifierMapping]

    def _count_mappings_by_relation_type(
        self: Self, relation_type: RelationType
    ) -> int:
        return sum(
            1 for mapping in self.mappings if mapping.relation_type == relation_type
        )

    @model_validator(mode="after")
    def validate_group(self) -> "MappingGroup":
        """Ensure MappingGroup contains a valid combination of mappings.

        Validates that:
        - At most one primary mapping per mapping group
        - At most one equivalent mapping per mapping group
        - Mapping group with alias mapping(s) requires a primary mapping
        - No duplicate mappings in a mappping group
        - All mappings in a mapping group share the same target_id, mapping_type,
          target_system and source_system

        Raises:
            ValueError: If validation fails or mapping type is unsupported
        """
        if not self.mappings:
            return self

        primary_mappings_count = self._count_mappings_by_relation_type(
            RelationType.primary
        )
        has_alias_mapping = (
            self._count_mappings_by_relation_type(RelationType.alias) > 0
        )

        if primary_mappings_count > 1:
            raise ValueError(
                f"MappingGroup for target '{self.target_id}' must contain at most one "
                "primary mapping."
            )

        if self._count_mappings_by_relation_type(RelationType.equivalent) > 1:
            raise ValueError(
                f"MappingGroup for target '{self.target_id}' must contain at most one "
                "equivalent mapping."
            )

        if has_alias_mapping and primary_mappings_count == 0:
            raise ValueError(
                f"MappingGroup for target '{self.target_id}' contains "
                "alias relations but no primary relation. Aliases require "
                "a primary unofficial identifier."
            )

        seen: set[tuple[str, UUID | None, RelationType]] = set()
        for mapping in self.mappings:
            mapping_key = (
                mapping.source_id,
                mapping.source_uuid,
                mapping.relation_type,
            )
            if mapping_key in seen:
                raise ValueError(
                    f"Duplicate mapping in group: source_id='{mapping.source_id}', "
                    f"source_uuid='{mapping.source_uuid}', "
                    f"relation_type='{mapping.relation_type}'."
                )

            if mapping.target_id != self.target_id:
                raise ValueError(
                    "All mappings in MappingGroup must share target_id "
                    f"'{self.target_id}'."
                )
            if mapping.mapping_type != self.mapping_type:
                raise ValueError(
                    "All mappings in MappingGroup must share mapping_type "
                    f"'{self.mapping_type}'."
                )
            if mapping.target_system != self.target_system:
                raise ValueError(
                    "All mappings in MappingGroup must share target_system "
                    f"'{self.target_system}'."
                )
            if mapping.source_system != self.source_system:
                raise ValueError(
                    "All mappings in MappingGroup must share source_system "
                    f"'{self.source_system}'."
                )
            if (
                mapping.target_uuid is not None
                and self.target_uuid is not None
                and mapping.target_uuid != self.target_uuid
            ):
                raise ValueError(
                    "All mappings in MappingGroup must share target_uuid "
                    f"'{self.target_uuid}'."
                )

            seen.add(mapping_key)

        return self

    @model_serializer(mode="plain")
    def serialize_for_display(self) -> dict[str, Any]:
        """Serialize to the display schema for API responses."""
        excluded_fields = {
            "source_system",
            "target_system",
            "mapping_type",
            "target_id",
            "target_uuid",
        }
        return {
            "official_name": self.target_id,
            "target_uuid": self.target_uuid,
            "mapping_type": self.mapping_type.value,
            "target_system": self.target_system.value,
            "source_system": self.source_system.value,
            "mappings": [
                {
                    key: value
                    for key, value in mapping.model_dump().items()
                    if key not in excluded_fields
                }
                for mapping in self.mappings
            ],
        }
