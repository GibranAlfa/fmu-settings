from __future__ import annotations

import copy
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

from fmu.datamodels.context.mappings import RelationType
from fmu.datamodels.fmu_results.global_configuration import Stratigraphy
from fmu.settings._resources.pydantic_resource_manager import PydanticResourceManager
from fmu.settings.models.mappings import (
    MappableIdentifierMapping,
    MappableMappings,
    Mappings,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    # Avoid circular dependency for type hint in __init__ only
    from fmu.datamodels.context.mappings import StratigraphyMappings, WellboreMappings
    from fmu.settings._fmu_dir import ProjectFMUDirectory


class MappingsManager(PydanticResourceManager[Mappings]):
    """Manages the .fmu mappings file."""

    fmu_dir: ProjectFMUDirectory

    def __init__(self: Self, fmu_dir: ProjectFMUDirectory) -> None:
        """Initializes the mappings resource manager."""
        super().__init__(fmu_dir, Mappings)

    @property
    def relative_path(self: Self) -> Path:
        """Returns the relative path to the mappings file."""
        return Path("mappings.json")

    @property
    def diff_list_keys(self: Self) -> Mapping[str, str]:
        """List field identity keys used for per-item diffing."""
        return {
            "stratigraphy.root": "__full__",
            "wellbore.root": "__full__",
        }

    @property
    def stratigraphy_mappings(self: Self) -> StratigraphyMappings:
        """Get all stratigraphy mappings."""
        return self.load().stratigraphy

    @property
    def wellbore_mappings(self: Self) -> WellboreMappings:
        """Get all wellbore mappings."""
        return self.load().wellbore

    def update_stratigraphy_mappings(
        self: Self, strat_mappings: StratigraphyMappings
    ) -> StratigraphyMappings:
        """Updates the stratigraphy mappings in the mappings resource."""
        mappings: Mappings = self.load() if self.exists else Mappings()

        old_mappings_dict = copy.deepcopy(mappings.model_dump())
        mappings.stratigraphy = strat_mappings
        self.save(mappings)

        self.fmu_dir.changelog.log_update_to_changelog(
            updates={"stratigraphy": mappings.stratigraphy},
            old_resource_dict=old_mappings_dict,
            relative_path=self.relative_path,
        )

        return self.stratigraphy_mappings

    def update_wellbore_mappings(
        self: Self, wellbore_mappings: WellboreMappings
    ) -> WellboreMappings:
        """Updates the wellbore mappings in the mappings resource."""
        mappings: Mappings = self.load() if self.exists else Mappings()

        old_mappings_dict = copy.deepcopy(mappings.model_dump())
        mappings.wellbore = wellbore_mappings
        self.save(mappings)

        self.fmu_dir.changelog.log_update_to_changelog(
            updates={"wellbore": mappings.wellbore},
            old_resource_dict=old_mappings_dict,
            relative_path=self.relative_path,
        )

        return self.wellbore_mappings

    def get_mappings_diff(self: Self, incoming_mappings: MappingsManager) -> Mappings:
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

    def merge_mappings(self: Self, incoming_mappings: MappingsManager) -> Mappings:
        """Merge the mappings from the incoming mappings resource.

        The current mappings will be updated with the mappings
        from the incoming resource.
        """
        mappings_diff = self.get_mappings_diff(incoming_mappings)
        return self.merge_changes(mappings_diff)

    def merge_changes(self: Self, changes: Mappings) -> Mappings:
        """Merge the mappings changes into the current mappings.

        The current mappings will be updated with the mappings
        in the change object.
        """
        if len(changes.stratigraphy) > 0 or len(self.stratigraphy_mappings) > 0:
            self.update_stratigraphy_mappings(changes.stratigraphy)
        if len(changes.wellbore) > 0 or len(self.wellbore_mappings) > 0:
            self.update_wellbore_mappings(changes.wellbore)
        return self.load()

    def get_mappable_mappings(
        self: Self,
        mappings: StratigraphyMappings | WellboreMappings,
    ) -> MappableMappings:
        """Return mappings that point from one system to another system.

        Stored mappings can describe relationships inside the same system, for
        example ``rms -> rms`` primaries and aliases. Downstream consumers often
        need mappable mappings instead, for example ``rms -> smda``.

        This method first finds same-system aliases and groups them by the
        same-system primary identifier they point to. It then keeps cross-system
        primary mappings and adds matching aliases to the same cross-system
        target. A same-system alias is only included when its primary identifier
        also has a cross-system primary mapping.

        Example:
        - ``rms -> rms: TopVolantis primary TopVolantis``
        - ``rms -> rms: TopVOLANTIS alias TopVolantis``
        - ``rms -> rms: TOP_VOLANTIS alias TopVolantis``
        - ``rms -> smda: TopVolantis primary VOLANTIS GP. Top``
        - ``rms -> rms: Seabase primary Seabase``
        - ``rms -> smda: Seabase unmappable``

        becomes:
        - ``rms -> smda: TopVolantis primary VOLANTIS GP. Top``
        - ``rms -> smda: TopVOLANTIS alias VOLANTIS GP. Top``
        - ``rms -> smda: TOP_VOLANTIS alias VOLANTIS GP. Top``

        The same-system mappings, and the unmappable ``Seabase`` mappings, are not
        included in the returned mappable mappings.
        """
        aliases_by_primary: dict[tuple[Any, Any, str], list[Any]] = {}

        # Group same-system aliases by the same-system primary id they point to.
        for mapping in mappings:
            if (
                mapping.source_system == mapping.target_system
                and mapping.relation_type == RelationType.alias
                and mapping.target_id is not None
            ):
                primary_key = (
                    mapping.mapping_type,
                    mapping.source_system,
                    mapping.target_id,
                )
                if primary_key not in aliases_by_primary:
                    aliases_by_primary[primary_key] = []
                aliases_by_primary[primary_key].append(mapping)

        mappable_mappings: list[MappableIdentifierMapping] = []

        # Keep cross-system primaries and add matching aliases to the same target.
        for mapping in mappings:
            if (
                mapping.source_system == mapping.target_system
                or mapping.relation_type != RelationType.primary
                or mapping.target_id is None
            ):
                continue

            mappable_mappings.append(
                MappableIdentifierMapping(
                    source_system=mapping.source_system,
                    target_system=mapping.target_system,
                    mapping_type=mapping.mapping_type,
                    relation_type=RelationType.primary,
                    source_id=mapping.source_id,
                    source_uuid=mapping.source_uuid,
                    target_id=mapping.target_id,
                    target_uuid=mapping.target_uuid,
                )
            )
            primary_key = (
                mapping.mapping_type,
                mapping.source_system,
                mapping.source_id,
            )
            for alias_mapping in aliases_by_primary.get(primary_key, []):
                mappable_mappings.append(
                    MappableIdentifierMapping(
                        source_system=mapping.source_system,
                        target_system=mapping.target_system,
                        mapping_type=mapping.mapping_type,
                        relation_type=RelationType.alias,
                        source_id=alias_mapping.source_id,
                        source_uuid=alias_mapping.source_uuid,
                        target_id=mapping.target_id,
                        target_uuid=mapping.target_uuid,
                    )
                )

        return MappableMappings(root=mappable_mappings)

    def build_global_config_stratigraphy(self) -> Stratigraphy:
        """Build a global config stratigraphy from mappings and RMS config.

        Combines stratigraphy mappings with RMS horizons and zones from the project
        config to produce a stratigraphy suitable for a GlobalConfiguration.
        """
        stratigraphy: dict[str, dict[str, Any]] = {}
        mappings = self.load() if self.exists else Mappings()
        stratigraphy_mappings = self.get_mappable_mappings(mappings.stratigraphy)

        primaries: dict[str, str] = {}  # source_id -> target_id
        aliases_by_target: dict[str, list[str]] = {}  # target_id -> [alias source_ids]

        # Stratigraphic entries from stratigraphy mappings
        for mapping in stratigraphy_mappings:
            if mapping.relation_type == RelationType.primary:
                primaries[mapping.source_id] = mapping.target_id
            elif mapping.relation_type == RelationType.alias:
                aliases_by_target.setdefault(mapping.target_id, []).append(
                    mapping.source_id
                )

        for source_id, target_id in primaries.items():
            entry: dict[str, Any] = {
                "stratigraphic": True,
                "name": target_id,
            }
            if aliases := aliases_by_target.get(target_id):
                entry["alias"] = aliases
            stratigraphy[source_id] = entry

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
