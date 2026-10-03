from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

from fmu.datamodels.context.mappings import (
    RelationType,
    StratigraphyMappings,
    WellboreMappings,
)
from fmu.datamodels.fmu_results.global_configuration import Stratigraphy
from fmu.settings._migrations import MigrationManager
from fmu.settings._migrations.mappings import MAPPINGS_MIGRATIONS
from fmu.settings._resources.pydantic_resource_manager import PydanticResourceManager
from fmu.settings.models.mappings import (
    InternalMappings,
    InternalStratigraphyMappings,
    InternalWellboreMappings,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    # Avoid circular dependency for type hint in __init__ only
    from fmu.settings._fmu_dir import ProjectFMUDirectory


class MappingsManager(PydanticResourceManager[InternalMappings]):
    """Manages the .fmu mappings file."""

    fmu_dir: ProjectFMUDirectory

    def __init__(self: Self, fmu_dir: ProjectFMUDirectory) -> None:
        """Initializes the mappings resource manager."""
        super().__init__(
            fmu_dir,
            InternalMappings,
            migration_manager=MigrationManager(
                InternalMappings,
                MAPPINGS_MIGRATIONS,
            ),
        )

    @property
    def relative_path(self: Self) -> Path:
        """Returns the relative path to the mappings file."""
        return Path("mappings.json")

    @property
    def diff_list_keys(self: Self) -> Mapping[str, str | tuple[str, ...]]:
        """List field identity keys used for per-item diffing."""
        return {
            "stratigraphy.root": (
                "mapping_type",
                "source_system",
                "target_system",
                "source_id",
            ),
            "wellbore.root": (
                "mapping_type",
                "source_system",
                "target_system",
                "source_id",
            ),
        }

    @property
    def internal_stratigraphy_mappings(self: Self) -> InternalStratigraphyMappings:
        """Get stratigraphy mappings stored in the internal .fmu mappings format."""
        return self.load().stratigraphy

    @property
    def internal_wellbore_mappings(self: Self) -> InternalWellboreMappings:
        """Get wellbore mappings stored in the internal .fmu mappings format."""
        return self.load().wellbore

    @property
    def stratigraphy_mappings(self: Self) -> StratigraphyMappings:
        """Get stratigraphy mappings as fmu-datamodels StratigraphyMappings."""
        return self.internal_stratigraphy_mappings.to_stratigraphy_mappings()

    @property
    def wellbore_mappings(self: Self) -> WellboreMappings:
        """Get wellbore mappings as fmu-datamodels WellboreMappings."""
        return self.internal_wellbore_mappings.to_wellbore_mappings()

    def update_internal_stratigraphy_mappings(
        self: Self, strat_mappings: InternalStratigraphyMappings
    ) -> InternalStratigraphyMappings:
        """Update stratigraphy mappings stored in the internal .fmu mappings format."""
        mappings: InternalMappings = self.load() if self.exists else InternalMappings()

        before = mappings.model_copy(deep=True)
        mappings.stratigraphy = strat_mappings
        self.save(mappings)

        self.fmu_dir.changelog.log_update_to_changelog(
            updates={"stratigraphy": mappings.stratigraphy},
            old_resource_dict=before.model_dump(),
            structured_diff=self.get_structured_model_diff(before, self.load()),
            relative_path=self.relative_path,
        )

        return self.internal_stratigraphy_mappings

    def update_internal_wellbore_mappings(
        self: Self, wellbore_mappings: InternalWellboreMappings
    ) -> InternalWellboreMappings:
        """Update wellbore mappings stored in the internal .fmu mappings format."""
        mappings: InternalMappings = self.load() if self.exists else InternalMappings()

        before = mappings.model_copy(deep=True)
        mappings.wellbore = wellbore_mappings
        self.save(mappings)

        self.fmu_dir.changelog.log_update_to_changelog(
            updates={"wellbore": mappings.wellbore},
            old_resource_dict=before.model_dump(),
            structured_diff=self.get_structured_model_diff(before, self.load()),
            relative_path=self.relative_path,
        )

        return self.internal_wellbore_mappings

    def get_mappings_diff(
        self: Self, incoming_mappings: MappingsManager
    ) -> InternalMappings:
        """Get mappings diff with the incoming mappings resource.

        All mappings from the incoming mappings resource are returned.
        """
        if self.exists and incoming_mappings.exists:
            return incoming_mappings.load()
        raise FileNotFoundError(
            "Mappings resources to diff must exist in both directories: "
            f"Current mappings resource exists: {self.exists}. "
            f"Incoming mappings resource exists: {incoming_mappings.exists}."
        )

    def merge_mappings(
        self: Self, incoming_mappings: MappingsManager
    ) -> InternalMappings:
        """Merge the mappings from the incoming mappings resource.

        The current mappings will be updated with the mappings
        from the incoming resource.
        """
        mappings_diff = self.get_mappings_diff(incoming_mappings)
        return self.merge_changes(mappings_diff)

    def merge_changes(self: Self, changes: InternalMappings) -> InternalMappings:
        """Merge the mappings changes into the current mappings.

        The current mappings will be updated with the mappings
        in the change object.
        """
        if (
            len(changes.stratigraphy) > 0
            or len(self.internal_stratigraphy_mappings) > 0
        ):
            self.update_internal_stratigraphy_mappings(changes.stratigraphy)
        if len(changes.wellbore) > 0 or len(self.internal_wellbore_mappings) > 0:
            self.update_internal_wellbore_mappings(changes.wellbore)
        return self.load()

    def build_global_config_stratigraphy(self) -> Stratigraphy:
        """Build a global config stratigraphy from mappings and RMS config.

        Combines the fmu-datamodels stratigraphy mappings with RMS horizons
        and zones from the project config to produce a stratigraphy suitable for a
        GlobalConfiguration.
        """
        stratigraphy: dict[str, dict[str, Any]] = {}
        stratigraphy_mappings = (
            self.stratigraphy_mappings if self.exists else StratigraphyMappings(root=[])
        )

        aliases_by_target_id: dict[
            str, list[str]
        ] = {}  # target_id -> [alias source_ids]

        # Stratigraphic entries from stratigraphy mappings
        for mapping in stratigraphy_mappings:
            if mapping.relation_type == RelationType.alias:
                aliases_by_target_id.setdefault(mapping.target_id, []).append(
                    mapping.source_id
                )

        for mapping in stratigraphy_mappings:
            if mapping.relation_type == RelationType.primary:
                entry: dict[str, Any] = {
                    "stratigraphic": True,
                    "name": mapping.target_id,
                    "uuid": mapping.target_uuid,
                }
                if aliases := aliases_by_target_id.get(mapping.target_id):
                    entry["alias"] = aliases
                stratigraphy[mapping.source_id] = entry

        # Non-stratigraphic entries from RMS
        rms_config = self.fmu_dir.get_config_value("rms")
        if rms_config:
            for horizon in rms_config.horizons or []:
                name = horizon.name
                if name not in stratigraphy:
                    stratigraphy[name] = {
                        "stratigraphic": False,
                        "name": name,
                    }
            for zone in rms_config.zones or []:
                name = zone.name
                if name not in stratigraphy:
                    stratigraphy[name] = {
                        "stratigraphic": False,
                        "name": name,
                    }

        return Stratigraphy.model_validate(stratigraphy)
