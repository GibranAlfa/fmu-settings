from __future__ import annotations

import copy
import csv
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

import pandas as pd

from fmu.datamodels.context.mappings import (
    DataSystem,
    MappingType,
    WellboreIdentifierMapping,
    WellboreMappings,
)
from fmu.datamodels.fmu_results.global_configuration import Stratigraphy
from fmu.settings._resources.pydantic_resource_manager import PydanticResourceManager
from fmu.settings.models.mappings import Mappings, RelationType

if TYPE_CHECKING:
    from collections.abc import Mapping

    # Avoid circular dependency for type hint in __init__ only
    from fmu.datamodels.context.mappings import StratigraphyMappings
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

    def _resolve_project_root_path(
        self: Self,
        relative_path: str | Path | None,
        *,
        default_path: str | Path,
        argument_name: str,
    ) -> tuple[Path, Path]:
        """Resolve a project-root-relative path and reject paths outside the root."""
        project_relative_path = (
            Path(relative_path) if relative_path is not None else Path(default_path)
        )
        resolved_path = (self.fmu_dir.base_path / project_relative_path).resolve()

        try:
            project_relative_path = resolved_path.relative_to(self.fmu_dir.base_path)
        except ValueError as error:
            raise ValueError(
                f"{argument_name} must stay within the project root"
            ) from error

        return project_relative_path, resolved_path

    def read_rms_eclipse_csv(
        self: Self, csv_relative_path: str | Path | None = None
    ) -> WellboreMappings:
        """Read well mappings from an rms_eclipse.csv-format file.

        Reads a CSV file relative to the project root, defaults to
        rms/input/well_modelling/well_info/rms_eclipse.csv, converts each
        RMS_WELL_NAME/ECLIPSE_WELL_NAME row into an RMS-to-simulator wellbore
        mapping, and returns the resulting WellboreMappings object.

        Args:
            csv_relative_path: Optional path relative to the project root.
                Defaults to rms/input/well_modelling/well_info/rms_eclipse.csv.

        Returns:
            The parsed well mappings.

        Raises:
            FileNotFoundError: If the CSV file does not exist.
            ValueError: If the path escapes the project root, required columns are
                missing, or a row has missing values.
        """
        _, csv_path = self._resolve_project_root_path(
            csv_relative_path,
            default_path="rms/input/well_modelling/well_info/rms_eclipse.csv",
            argument_name="csv_relative_path",
        )

        if not csv_path.is_file():
            raise FileNotFoundError(f"CSV file not found: '{csv_path}'")

        with csv_path.open(encoding="utf-8", newline="") as file_handle:
            reader = csv.DictReader(file_handle)
            fieldnames = reader.fieldnames or []
            required_headers = {"RMS_WELL_NAME", "ECLIPSE_WELL_NAME"}
            missing_headers = required_headers.difference(fieldnames)
            if missing_headers:
                missing_headers_text = ", ".join(sorted(missing_headers))
                raise ValueError(
                    f"CSV file is missing required columns: {missing_headers_text}"
                )

            mappings: list[WellboreIdentifierMapping] = []
            for row_number, row in enumerate(reader, start=2):
                source_id = (row.get("RMS_WELL_NAME") or "").strip()
                target_id = (row.get("ECLIPSE_WELL_NAME") or "").strip()

                if not source_id and not target_id:
                    continue

                if not source_id or not target_id:
                    raise ValueError(
                        f"CSV row has missing well mapping values at line {row_number}"
                    )

                mappings.append(
                    WellboreIdentifierMapping(
                        source_system=DataSystem.rms,
                        target_system=DataSystem.simulator,
                        mapping_type=MappingType.wellbore,
                        relation_type=RelationType.primary,
                        source_id=source_id,
                        source_uuid=None,
                        target_id=target_id,
                        target_uuid=None,
                    )
                )

        return WellboreMappings(root=mappings)

    def write_rms_eclipse_csv(
        self: Self,
        wellbore_mappings: WellboreMappings,
        csv_relative_path: str | Path | None = None,
    ) -> Path:
        """Write wellbore mappings to an rms_eclipse.csv-format file.

        Writes a CSV file relative to the project root, defaults to
        rms/input/well_modelling/well_info/rms_eclipse.csv, using the rms_eclipse.csv
        two-column format with headers RMS_WELL_NAME and ECLIPSE_WELL_NAME.
        If the target CSV file already exists, it is overwritten.

        Only RMS-to-simulator primary wellbore mappings are written with this
        format. Any other mapping shape is ignored. A ValueError is raised if
        there are no representable mappings to write.

        Args:
            wellbore_mappings: Wellbore mappings to serialize.
            csv_relative_path: Optional output path relative to the project root.
                Defaults to rms/input/well_modelling/well_info/rms_eclipse.csv.

        Returns:
            The path to the written CSV file, relative to the project root.

        Raises:
            PermissionError: If the project is locked by another process.
            ValueError: If the path escapes the project root or there are no
                RMS-to-simulator primary wellbore mappings to write.
        """
        self.fmu_dir._lock.ensure_can_write()
        csv_relative_path, csv_path = self._resolve_project_root_path(
            csv_relative_path,
            default_path="rms/input/well_modelling/well_info/rms_eclipse.csv",
            argument_name="csv_relative_path",
        )

        rows: list[dict[str, str]] = []
        for mapping in wellbore_mappings:
            if (
                mapping.source_system == DataSystem.rms
                and mapping.target_system == DataSystem.simulator
                and mapping.mapping_type == MappingType.wellbore
                and mapping.relation_type == RelationType.primary
            ):
                rows.append(
                    {
                        "RMS_WELL_NAME": mapping.source_id,
                        "ECLIPSE_WELL_NAME": mapping.target_id,
                    }
                )

        if not rows:
            raise ValueError(
                "No RMS-to-simulator primary wellbore mappings available to "
                "write to rms_eclipse.csv"
            )

        csv_path.parent.mkdir(parents=True, exist_ok=True)

        with csv_path.open("w", encoding="utf-8", newline="") as file_handle:
            writer = csv.DictWriter(
                file_handle,
                fieldnames=["RMS_WELL_NAME", "ECLIPSE_WELL_NAME"],
            )
            writer.writeheader()
            writer.writerows(rows)

        return csv_relative_path

    def write_rms_eclipse_renaming_table(
        self: Self,
        wellbore_mappings: WellboreMappings,
        renaming_table_relative_path: str | Path | None = None,
    ) -> Path:
        """Write wellbore mappings to an rms_eclipse.renaming_table file.

        Writes a renaming table file relative to the project root,
        defaults to rms/input/well_modelling/well_info/rms_eclipse.renaming_table,
        with the header row ``SETNAMES``, ``rms``, and ``eclipse`` separated by
        tab characters, followed by one source and one target identifier per line.

        Only RMS-to-simulator primary wellbore mappings are written with this
        format. Any other mapping shape is ignored. A ValueError is raised if
        there are no representable mappings to write.

        Args:
            wellbore_mappings: Wellbore mappings to serialize.
            renaming_table_relative_path: Optional output path relative to the
                project root. Defaults to
                rms/input/well_modelling/well_info/rms_eclipse.renaming_table.

        Returns:
            The path to the written renaming table, relative to the project root.

        Raises:
            PermissionError: If the project is locked by another process.
            ValueError: If the path escapes the project root or there are no
                RMS-to-simulator primary wellbore mappings to write.
        """
        self.fmu_dir._lock.ensure_can_write()
        renaming_table_relative_path, renaming_table_path = (
            self._resolve_project_root_path(
                renaming_table_relative_path,
                default_path="rms/input/well_modelling/well_info/rms_eclipse.renaming_table",
                argument_name="renaming_table_relative_path",
            )
        )

        rows: list[tuple[str, str]] = []
        for mapping in wellbore_mappings:
            if (
                mapping.source_system == DataSystem.rms
                and mapping.target_system == DataSystem.simulator
                and mapping.mapping_type == MappingType.wellbore
                and mapping.relation_type == RelationType.primary
            ):
                rows.append((mapping.source_id, mapping.target_id))

        if not rows:
            raise ValueError(
                "No RMS-to-simulator primary wellbore mappings available to "
                "write to rms_eclipse.renaming_table"
            )

        renaming_table_path.parent.mkdir(parents=True, exist_ok=True)

        with renaming_table_path.open("w", encoding="utf-8", newline="") as file_handle:
            file_handle.write("SETNAMES rms\teclipse\n")
            for source_id, target_id in rows:
                file_handle.write(f"{source_id}\t{target_id}\n")

        return renaming_table_relative_path

    def write_pdm_rms_renaming_table(
        self: Self,
        wellbore_mappings: WellboreMappings,
        renaming_table_relative_path: str | Path | None = None,
    ) -> Path:
        """Write wellbore mappings to a pdm_rms.renaming_table file.

        Writes a renaming table file relative to the project root,
        defaults to rms/input/well_modelling/well_info/pdm_rms.renaming_table,
        with the header row ``SETNAMES pdm`` and ``rms`` separated by a tab
        character, followed by one source and one target identifier per line.

        Only PDM-to-RMS primary wellbore mappings are written with this format.
        Any other mapping shape is ignored. A ValueError is raised if there are
        no representable mappings to write.

        Args:
            wellbore_mappings: Wellbore mappings to serialize.
            renaming_table_relative_path: Optional output path relative to the
                project root. Defaults to
                rms/input/well_modelling/well_info/pdm_rms.renaming_table.

        Returns:
            The path to the written renaming table, relative to the project root.

        Raises:
            PermissionError: If the project is locked by another process.
            ValueError: If the path escapes the project root or there are no
                PDM-to-RMS primary wellbore mappings to write.
        """
        self.fmu_dir._lock.ensure_can_write()
        renaming_table_relative_path, renaming_table_path = (
            self._resolve_project_root_path(
                renaming_table_relative_path,
                default_path="rms/input/well_modelling/well_info/pdm_rms.renaming_table",
                argument_name="renaming_table_relative_path",
            )
        )

        rows: list[tuple[str, str]] = []
        for mapping in wellbore_mappings:
            if (
                mapping.source_system == DataSystem.pdm
                and mapping.target_system == DataSystem.rms
                and mapping.mapping_type == MappingType.wellbore
                and mapping.relation_type == RelationType.primary
            ):
                rows.append((mapping.source_id, mapping.target_id))

        if not rows:
            raise ValueError(
                "No PDM-to-RMS primary wellbore mappings available to "
                "write to pdm_rms.renaming_table"
            )

        renaming_table_path.parent.mkdir(parents=True, exist_ok=True)

        with renaming_table_path.open("w", encoding="utf-8", newline="") as file_handle:
            file_handle.write("SETNAMES pdm\trms\n")
            for source_id, target_id in rows:
                file_handle.write(f"{source_id}\t{target_id}\n")

        return renaming_table_relative_path

    def wellbore_mappings_to_dataframe(
        self: Self, wellbore_mappings: WellboreMappings
    ) -> dict[str, pd.DataFrame]:
        """Convert RMS wellbore mappings to one dataframe per target system.

        Each returned dataframe has the fixed source column ``rms`` and one
        target-system column such as ``simulator`` or ``smda``.

        Args:
            wellbore_mappings: Wellbore mappings to convert. All mappings must use
                ``DataSystem.rms`` as the source system, ``MappingType.wellbore``
                as the mapping type, and ``RelationType.primary`` as the relation
                type to be included. Mappings that do not match all three are
                ignored.

        Returns:
            A dictionary keyed by target-system name. Each value is a dataframe
            containing the RMS source ids and the corresponding target ids for
            that target system.

            Example return value when both simulator and SMDA mappings are
            present:

            {
                "simulator": pd.DataFrame(
                    [{"rms": "30_9-B-43_A", "simulator": "B43A"}]
                ),
                "smda": pd.DataFrame(
                    [{"rms": "30_9-B-21_C", "smda": "NO 30/9-B-21 C"}]
                ),
            }

            Example usage from an rms_eclipse.csv file:

            from fmu.settings import get_fmu_directory

            fmu_dir = get_fmu_directory("/path/to/project")
            # Read directly from rms/input/well_modelling/well_info/rms_eclipse.csv
            wellbore_mappings = fmu_dir.mappings.read_rms_eclipse_csv()
            # Or pass a custom path relative to the project root:
            # wellbore_mappings = fmu_dir.mappings.read_rms_eclipse_csv(
            #     "data/custom/rms_eclipse.csv"
            # )
            df = fmu_dir.mappings.wellbore_mappings_to_dataframe(wellbore_mappings)
            simulator_df = df["simulator"]
            smda_df = df["smda"]

            Example usage from mappings.json in the project .fmu directory:

            from fmu.settings import get_fmu_directory

            fmu_dir = get_fmu_directory("/path/to/project")
            wellbore_mappings = fmu_dir.mappings.wellbore_mappings
            df = fmu_dir.mappings.wellbore_mappings_to_dataframe(wellbore_mappings)
            simulator_df = df["simulator"]
            smda_df = df["smda"]

        """
        grouped_rows: dict[str, list[dict[str, str]]] = {}
        for mapping in wellbore_mappings:
            if (
                mapping.source_system == DataSystem.rms
                and mapping.mapping_type == MappingType.wellbore
                and mapping.relation_type == RelationType.primary
            ):
                target_system = mapping.target_system.value
                grouped_rows.setdefault(target_system, []).append(
                    {
                        "rms": mapping.source_id,
                        target_system: mapping.target_id,
                    }
                )

        return {
            target_system: pd.DataFrame(rows, columns=["rms", target_system])
            for target_system, rows in grouped_rows.items()
        }

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

    def build_global_config_stratigraphy(self) -> Stratigraphy:  # noqa: PLR0912
        """Build a global config stratigraphy from mappings and RMS config.

        Combines stratigraphy mappings with RMS horizons and zones from the project
        config to produce a stratigraphy suitable for a GlobalConfiguration.
        """
        stratigraphy: dict[str, dict[str, Any]] = {}
        mappings = self.load() if self.exists else Mappings()

        primaries: dict[str, str] = {}  # source_id -> target_id
        aliases_by_target: dict[str, list[str]] = {}  # target_id -> [alias source_ids]
        equivalents_by_target: dict[str, list[str]] = {}

        # Stratigraphic entries from stratigraphy mappings
        for mapping in mappings.stratigraphy:
            if mapping.relation_type == RelationType.primary:
                primaries[mapping.source_id] = mapping.target_id
            elif mapping.relation_type == RelationType.alias:
                aliases_by_target.setdefault(mapping.target_id, []).append(
                    mapping.source_id
                )
            elif mapping.relation_type == RelationType.equivalent:
                equivalents_by_target.setdefault(mapping.target_id, []).append(
                    mapping.source_id
                )

        primary_targets = set(primaries.values())
        for source_id, target_id in primaries.items():
            entry: dict[str, Any] = {
                "stratigraphic": True,
                "name": target_id,
            }
            if aliases := aliases_by_target.get(target_id):
                entry["alias"] = aliases
            stratigraphy[source_id] = entry

        # Keep equivalent-only mappings as valid stratigraphic entries even when
        # there is no separate primary RMS identifier for the same official name
        for target_id in equivalents_by_target:
            if target_id in primary_targets:
                continue
            stratigraphy[target_id] = {
                "stratigraphic": True,
                "name": target_id,
            }

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
