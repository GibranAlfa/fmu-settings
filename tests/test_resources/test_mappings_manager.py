"""Tests for MappingsManager."""

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from fmu.datamodels.context.mappings import (
    DataSystem,
    MappingType,
    RelationType,
    StratigraphyIdentifierMapping,
    StratigraphyMappings,
    WellboreIdentifierMapping,
    WellboreMappings,
)

from fmu.settings._drogon import GLOBAL_CONFIG_STRATIGRAPHY
from fmu.settings._fmu_dir import ProjectFMUDirectory
from fmu.settings._resources.mappings_manager import MappingsManager
from fmu.settings.models._enums import ChangeType
from fmu.settings.models.diff import ListFieldDiff
from fmu.settings.models.mappings import Mappings

if TYPE_CHECKING:
    from fmu.settings.models.change_info import ChangeInfo
    from fmu.settings.models.log import Log


def make_wellbore_identifier_mapping(
    **overrides: Any,
) -> WellboreIdentifierMapping:
    """Build a wellbore mapping with defaults and possible local test overrides."""
    mapping_data: dict[str, Any] = {
        "source_system": DataSystem.rms,
        "target_system": DataSystem.simulator,
        "mapping_type": MappingType.wellbore,
        "relation_type": RelationType.primary,
        "source_id": "30_9-B-43_A",
        "source_uuid": None,
        "target_id": "B43A",
        "target_uuid": None,
    }
    mapping_data.update(overrides)

    return WellboreIdentifierMapping(
        **mapping_data,
    )


@pytest.fixture
def wellbore_mappings() -> WellboreMappings:
    """Returns a valid WellboreMappings object."""
    return WellboreMappings(root=[make_wellbore_identifier_mapping()])


@pytest.fixture
def stratigraphy_mappings() -> StratigraphyMappings:
    """Returns a valid StratigraphyMappings object."""
    return StratigraphyMappings(
        root=[
            StratigraphyIdentifierMapping(
                source_system=DataSystem.rms,
                target_system=DataSystem.smda,
                relation_type=RelationType.primary,
                source_id="TopVolantis",
                target_id="VOLANTIS GP. Top",
            ),
            StratigraphyIdentifierMapping(
                source_system=DataSystem.rms,
                target_system=DataSystem.smda,
                relation_type=RelationType.alias,
                source_id="TopVOLANTIS",
                target_id="VOLANTIS GP. Top",
            ),
            StratigraphyIdentifierMapping(
                source_system=DataSystem.rms,
                target_system=DataSystem.smda,
                relation_type=RelationType.alias,
                source_id="TOP_VOLANTIS",
                target_id="VOLANTIS GP. Top",
            ),
        ]
    )


def test_mappings_manager_instantiation(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Tests basic facts about the Mappings resource Manager."""
    mappings_manager: MappingsManager = MappingsManager(fmu_dir)

    assert mappings_manager.fmu_dir == fmu_dir
    assert mappings_manager.relative_path == Path("mappings.json")

    expected_path = mappings_manager.fmu_dir.path / mappings_manager.relative_path
    assert mappings_manager.path == expected_path
    assert mappings_manager.model_class == Mappings
    assert mappings_manager.exists is False

    with pytest.raises(
        FileNotFoundError, match="Resource file for 'MappingsManager' not found"
    ):
        mappings_manager.load()


def test_mappings_manager_update_stratigraphy_mappings_overwrites_mappings(
    fmu_dir: ProjectFMUDirectory,
    stratigraphy_mappings: StratigraphyMappings,
) -> None:
    """Tests that updating stratigraphy mappings overwrites existing mappings."""
    mappings_manager: MappingsManager = MappingsManager(fmu_dir)
    assert mappings_manager.exists is False

    mappings_manager.update_stratigraphy_mappings(stratigraphy_mappings)
    assert mappings_manager.exists is True
    mappings = mappings_manager.load()
    expected_no_of_mappings = 3
    assert len(mappings.stratigraphy) == expected_no_of_mappings
    assert mappings.stratigraphy[0] == stratigraphy_mappings[0]

    new_mapping = StratigraphyIdentifierMapping(
        source_system=DataSystem.rms,
        target_system=DataSystem.smda,
        relation_type=RelationType.primary,
        source_id="TopViking",
        target_id="VIKING GP. Top",
    )

    mappings_manager.update_stratigraphy_mappings(
        StratigraphyMappings(root=[new_mapping])
    )

    # Assert that existing mappings are overwritten
    mappings = mappings_manager.load()
    assert len(mappings.stratigraphy) == 1
    assert mappings.stratigraphy[0] == new_mapping


def test_mappings_manager_update_stratigraphy_mappings_writes_to_changelog(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Tests that each update of the stratigraphy mappings, writes to the changelog."""
    mappings_manager: MappingsManager = MappingsManager(fmu_dir)
    new_mappings = StratigraphyMappings(
        root=[
            StratigraphyIdentifierMapping(
                source_system=DataSystem.rms,
                target_system=DataSystem.smda,
                relation_type=RelationType.primary,
                source_id="TopViking",
                target_id="VIKING GP. Top",
            )
        ]
    )
    mappings_manager.update_stratigraphy_mappings(new_mappings)

    changelog: Log[ChangeInfo] = mappings_manager.fmu_dir._changelog.load()
    assert len(changelog) == 1
    assert changelog[0].change_type == ChangeType.update
    assert changelog[0].file == "mappings.json"
    assert changelog[0].key == "stratigraphy"
    assert f"New value: {new_mappings.model_dump()}" in changelog[0].change

    mappings_manager.update_stratigraphy_mappings(new_mappings)
    mappings_manager.update_stratigraphy_mappings(new_mappings)

    expected_no_of_mappings = 3
    assert len(mappings_manager.fmu_dir._changelog.load()) == expected_no_of_mappings


def test_mappings_manager_update_wellbore_mappings_overwrites_mappings(
    fmu_dir: ProjectFMUDirectory,
    wellbore_mappings: WellboreMappings,
) -> None:
    """Tests that updating wellbore mappings overwrites existing mappings."""
    mappings_manager: MappingsManager = MappingsManager(fmu_dir)
    assert mappings_manager.exists is False

    mappings_manager.update_wellbore_mappings(wellbore_mappings)
    assert mappings_manager.exists is True
    mappings = mappings_manager.load()
    assert len(mappings.wellbore) == 1
    assert mappings.wellbore[0] == wellbore_mappings[0]

    new_mapping = WellboreIdentifierMapping(
        source_system=DataSystem.rms,
        target_system=DataSystem.simulator,
        mapping_type=MappingType.wellbore,
        relation_type=RelationType.primary,
        source_id="30_9-B-43_B",
        source_uuid=None,
        target_id="B43B",
        target_uuid=None,
    )

    mappings_manager.update_wellbore_mappings(WellboreMappings(root=[new_mapping]))

    # Assert that existing mappings are overwritten
    mappings = mappings_manager.load()
    assert len(mappings.wellbore) == 1
    assert mappings.wellbore[0] == new_mapping


def test_mappings_manager_update_wellbore_mappings_writes_to_changelog(
    fmu_dir: ProjectFMUDirectory,
    wellbore_mappings: WellboreMappings,
) -> None:
    """Tests that each update of the wellbore mappings writes to the changelog."""
    mappings_manager: MappingsManager = MappingsManager(fmu_dir)

    mappings_manager.update_wellbore_mappings(wellbore_mappings)

    changelog: Log[ChangeInfo] = mappings_manager.fmu_dir._changelog.load()
    assert len(changelog) == 1
    assert changelog[0].change_type == ChangeType.update
    assert changelog[0].file == "mappings.json"
    assert changelog[0].key == "wellbore"
    assert f"New value: {wellbore_mappings.model_dump()}" in changelog[0].change

    mappings_manager.update_wellbore_mappings(wellbore_mappings)
    mappings_manager.update_wellbore_mappings(wellbore_mappings)

    expected_no_of_mappings = 3
    assert len(mappings_manager.fmu_dir._changelog.load()) == expected_no_of_mappings


def test_read_rms_eclipse_csv_default_path(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Default project-root-relative CSV path is converted to a WellboreMappings."""
    expected_mapping_count = 2
    csv_path = fmu_dir.base_path / "rms/input/well_modelling/well_info/rms_eclipse.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.write_text(
        "RMS_WELL_NAME,ECLIPSE_WELL_NAME\n30_9-B-43_A,B43A\nMLT_30_9-B-39_A,B39A\n",
        encoding="utf-8",
    )

    mappings_manager = MappingsManager(fmu_dir)

    well_mappings = mappings_manager.read_rms_eclipse_csv()

    assert len(well_mappings) == expected_mapping_count
    assert mappings_manager.exists is False
    assert well_mappings[0] == make_wellbore_identifier_mapping()


def test_read_rms_eclipse_csv_custom_path(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Custom project-root-relative CSV path is supported."""
    csv_relative_path = Path("data/custom/rms_eclipse.csv")
    csv_path = fmu_dir.base_path / csv_relative_path
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.write_text(
        "RMS_WELL_NAME,ECLIPSE_WELL_NAME\n30_9-B-43_A,B43A\n",
        encoding="utf-8",
    )

    mappings_manager = MappingsManager(fmu_dir)

    well_mappings = mappings_manager.read_rms_eclipse_csv(csv_relative_path)

    assert well_mappings == WellboreMappings(root=[make_wellbore_identifier_mapping()])


def test_read_rms_eclipse_csv_raises_for_missing_file(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Missing CSV files should raise a FileNotFoundError."""
    mappings_manager = MappingsManager(fmu_dir)

    with pytest.raises(FileNotFoundError, match="CSV file not found"):
        mappings_manager.read_rms_eclipse_csv("data/missing/rms_eclipse.csv")


@pytest.mark.parametrize(
    "csv_relative_path",
    [Path("../outside.csv"), Path("/tmp/outside.csv")],
)
def test_read_rms_eclipse_csv_raises_for_path_outside_project_root(
    fmu_dir: ProjectFMUDirectory,
    csv_relative_path: Path,
) -> None:
    """Read paths must stay within the project root."""
    mappings_manager = MappingsManager(fmu_dir)

    with pytest.raises(
        ValueError,
        match="csv_relative_path must stay within the project root",
    ):
        mappings_manager.read_rms_eclipse_csv(csv_relative_path)


def test_read_rms_eclipse_csv_raises_for_missing_headers(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Missing required CSV headers should raise a ValueError."""
    csv_relative_path = Path("data/custom/invalid_headers.csv")
    csv_path = fmu_dir.base_path / csv_relative_path
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.write_text(
        "RMS_WELL_NAME,WRONG_HEADER\n30_9-B-43_A,B43A\n",
        encoding="utf-8",
    )

    mappings_manager = MappingsManager(fmu_dir)

    with pytest.raises(
        ValueError,
        match="CSV file is missing required columns: ECLIPSE_WELL_NAME",
    ):
        mappings_manager.read_rms_eclipse_csv(csv_relative_path)


def test_read_rms_eclipse_csv_skips_empty_rows(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Rows with both values blank should be ignored."""
    csv_relative_path = Path("data/custom/empty_rows.csv")
    csv_path = fmu_dir.base_path / csv_relative_path
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.write_text(
        "RMS_WELL_NAME,ECLIPSE_WELL_NAME\n,\n30_9-B-43_A,B43A\n",
        encoding="utf-8",
    )

    mappings_manager = MappingsManager(fmu_dir)
    well_mappings = mappings_manager.read_rms_eclipse_csv(csv_relative_path)

    assert well_mappings == WellboreMappings(root=[make_wellbore_identifier_mapping()])


def test_read_rms_eclipse_csv_raises_for_partial_row(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Rows with one blank value should raise a ValueError."""
    csv_relative_path = Path("data/custom/partial_row.csv")
    csv_path = fmu_dir.base_path / csv_relative_path
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.write_text(
        "RMS_WELL_NAME,ECLIPSE_WELL_NAME\n30_9-B-43_A,\n",
        encoding="utf-8",
    )

    mappings_manager = MappingsManager(fmu_dir)

    with pytest.raises(
        ValueError,
        match="CSV row has missing well mapping values at line 2",
    ):
        mappings_manager.read_rms_eclipse_csv(csv_relative_path)


def test_write_rms_eclipse_csv_writes_expected_format(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Well mappings are written using the rms_eclipse.csv format."""
    mappings_manager = MappingsManager(fmu_dir)
    csv_relative_path = Path("data/custom/rms_eclipse.csv")

    written_path = mappings_manager.write_rms_eclipse_csv(
        WellboreMappings(root=[make_wellbore_identifier_mapping()]),
        csv_relative_path=csv_relative_path,
    )

    assert written_path == csv_relative_path
    assert (fmu_dir.base_path / written_path).read_text(encoding="utf-8") == (
        "RMS_WELL_NAME,ECLIPSE_WELL_NAME\n30_9-B-43_A,B43A\n"
    )


def test_write_rms_eclipse_csv_uses_default_path(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Default write path is the project rms_eclipse.csv location."""
    mappings_manager = MappingsManager(fmu_dir)

    written_path = mappings_manager.write_rms_eclipse_csv(
        WellboreMappings(root=[make_wellbore_identifier_mapping()])
    )

    assert written_path == Path("rms/input/well_modelling/well_info/rms_eclipse.csv")
    assert (fmu_dir.base_path / written_path).read_text(encoding="utf-8") == (
        "RMS_WELL_NAME,ECLIPSE_WELL_NAME\n30_9-B-43_A,B43A\n"
    )


def test_write_rms_eclipse_csv_ignores_non_simulator_mappings(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Mixed input writes only RMS-to-simulator primary wellbore mappings."""
    mappings_manager = MappingsManager(fmu_dir)
    csv_relative_path = Path("data/custom/rms_eclipse.csv")

    written_path = mappings_manager.write_rms_eclipse_csv(
        WellboreMappings(
            root=[
                make_wellbore_identifier_mapping(),
                make_wellbore_identifier_mapping(
                    target_system=DataSystem.smda,
                    source_id="30_9-B-21_C",
                    target_id="NO 30/9-B-21 C",
                ),
            ]
        ),
        csv_relative_path=csv_relative_path,
    )

    assert written_path == csv_relative_path
    assert (fmu_dir.base_path / written_path).read_text(encoding="utf-8") == (
        "RMS_WELL_NAME,ECLIPSE_WELL_NAME\n30_9-B-43_A,B43A\n"
    )


def test_write_rms_eclipse_csv_raises_and_preserves_file_when_no_rows_match(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """CSV export raises and preserves the file when no mappings are exportable."""
    mappings_manager = MappingsManager(fmu_dir)
    csv_relative_path = Path("data/custom/rms_eclipse.csv")
    csv_path = fmu_dir.base_path / csv_relative_path
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.write_text("existing csv content\n", encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="No RMS-to-simulator primary wellbore mappings available",
    ):
        mappings_manager.write_rms_eclipse_csv(
            WellboreMappings(
                root=[
                    make_wellbore_identifier_mapping(
                        target_system=DataSystem.smda,
                        target_id="NO 30/9-B-43 A",
                    ),
                    make_wellbore_identifier_mapping(
                        source_system=DataSystem.smda,
                        source_id="NO 30/9-B-21 C",
                        target_id="B21C",
                    ),
                ]
            ),
            csv_relative_path=csv_relative_path,
        )

    assert csv_path.read_text(encoding="utf-8") == "existing csv content\n"


def test_write_rms_eclipse_renaming_table_writes_expected_format(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Well mappings are written using the renaming-table format."""
    mappings_manager = MappingsManager(fmu_dir)
    renaming_table_relative_path = Path("data/custom/rms_eclipse.renaming_table")

    written_path = mappings_manager.write_rms_eclipse_renaming_table(
        WellboreMappings(root=[make_wellbore_identifier_mapping()]),
        renaming_table_relative_path=renaming_table_relative_path,
    )

    assert written_path == renaming_table_relative_path
    assert (fmu_dir.base_path / written_path).read_text(encoding="utf-8") == (
        "SETNAMES rms\teclipse\n30_9-B-43_A\tB43A\n"
    )


def test_write_rms_eclipse_renaming_table_uses_default_path(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Default write path is the project rms_eclipse.renaming_table location."""
    mappings_manager = MappingsManager(fmu_dir)

    written_path = mappings_manager.write_rms_eclipse_renaming_table(
        WellboreMappings(root=[make_wellbore_identifier_mapping()])
    )

    assert written_path == Path(
        "rms/input/well_modelling/well_info/rms_eclipse.renaming_table"
    )
    assert (fmu_dir.base_path / written_path).read_text(encoding="utf-8") == (
        "SETNAMES rms\teclipse\n30_9-B-43_A\tB43A\n"
    )


def test_write_rms_eclipse_renaming_table_ignores_non_simulator_mappings(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Mixed input writes only RMS-to-simulator primary wellbore mappings."""
    mappings_manager = MappingsManager(fmu_dir)
    renaming_table_relative_path = Path("data/custom/rms_eclipse.renaming_table")

    written_path = mappings_manager.write_rms_eclipse_renaming_table(
        WellboreMappings(
            root=[
                make_wellbore_identifier_mapping(),
                make_wellbore_identifier_mapping(
                    target_system=DataSystem.smda,
                    source_id="30_9-B-21_C",
                    target_id="NO 30/9-B-21 C",
                ),
            ]
        ),
        renaming_table_relative_path=renaming_table_relative_path,
    )

    assert written_path == renaming_table_relative_path
    assert (fmu_dir.base_path / written_path).read_text(encoding="utf-8") == (
        "SETNAMES rms\teclipse\n30_9-B-43_A\tB43A\n"
    )


def test_write_renaming_table_raises_and_preserves_file_when_no_rows_match(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Renaming-table export raises and preserves the file when empty."""
    mappings_manager = MappingsManager(fmu_dir)
    renaming_table_relative_path = Path("data/custom/rms_eclipse.renaming_table")
    renaming_table_path = fmu_dir.base_path / renaming_table_relative_path
    renaming_table_path.parent.mkdir(parents=True, exist_ok=True)
    renaming_table_path.write_text("existing renaming table\n", encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="No RMS-to-simulator primary wellbore mappings available",
    ):
        mappings_manager.write_rms_eclipse_renaming_table(
            WellboreMappings(
                root=[
                    make_wellbore_identifier_mapping(
                        target_system=DataSystem.smda,
                        target_id="NO 30/9-B-43 A",
                    ),
                    make_wellbore_identifier_mapping(
                        source_system=DataSystem.smda,
                        source_id="NO 30/9-B-21 C",
                        target_id="B21C",
                    ),
                ]
            ),
            renaming_table_relative_path=renaming_table_relative_path,
        )

    assert renaming_table_path.read_text(encoding="utf-8") == (
        "existing renaming table\n"
    )


def test_write_pdm_rms_renaming_table_writes_expected_format(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Well mappings are written using the PDM-to-RMS renaming-table format."""
    mappings_manager = MappingsManager(fmu_dir)
    renaming_table_relative_path = Path("data/custom/pdm_rms.renaming_table")

    written_path = mappings_manager.write_pdm_rms_renaming_table(
        WellboreMappings(
            root=[
                make_wellbore_identifier_mapping(
                    source_system=DataSystem.pdm,
                    target_system=DataSystem.rms,
                    source_id="30/9-B-43 A",
                    target_id="30_9-B-43_A",
                )
            ]
        ),
        renaming_table_relative_path=renaming_table_relative_path,
    )

    assert written_path == renaming_table_relative_path
    assert (fmu_dir.base_path / written_path).read_text(encoding="utf-8") == (
        "SETNAMES pdm\trms\n30/9-B-43 A\t30_9-B-43_A\n"
    )


def test_write_pdm_rms_renaming_table_uses_default_path(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Default write path is the project pdm_rms.renaming_table location."""
    mappings_manager = MappingsManager(fmu_dir)

    written_path = mappings_manager.write_pdm_rms_renaming_table(
        WellboreMappings(
            root=[
                make_wellbore_identifier_mapping(
                    source_system=DataSystem.pdm,
                    target_system=DataSystem.rms,
                    source_id="30/9-B-43 A",
                    target_id="30_9-B-43_A",
                )
            ]
        )
    )

    assert written_path == Path(
        "rms/input/well_modelling/well_info/pdm_rms.renaming_table"
    )
    assert (fmu_dir.base_path / written_path).read_text(encoding="utf-8") == (
        "SETNAMES pdm\trms\n30/9-B-43 A\t30_9-B-43_A\n"
    )


def test_write_pdm_rms_renaming_table_ignores_non_matching_mappings(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Mixed input writes only PDM-to-RMS primary wellbore mappings."""
    mappings_manager = MappingsManager(fmu_dir)
    renaming_table_relative_path = Path("data/custom/pdm_rms.renaming_table")

    written_path = mappings_manager.write_pdm_rms_renaming_table(
        WellboreMappings(
            root=[
                make_wellbore_identifier_mapping(
                    source_system=DataSystem.pdm,
                    target_system=DataSystem.rms,
                    source_id="30/9-B-43 A",
                    target_id="30_9-B-43_A",
                ),
                make_wellbore_identifier_mapping(
                    source_system=DataSystem.rms,
                    target_system=DataSystem.simulator,
                    source_id="30_9-B-21_C",
                    target_id="B21C",
                ),
            ]
        ),
        renaming_table_relative_path=renaming_table_relative_path,
    )

    assert written_path == renaming_table_relative_path
    assert (fmu_dir.base_path / written_path).read_text(encoding="utf-8") == (
        "SETNAMES pdm\trms\n30/9-B-43 A\t30_9-B-43_A\n"
    )


def test_write_pdm_rms_renaming_table_raises_and_preserves_file_when_no_rows_match(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """PDM-to-RMS renaming-table export raises and preserves the file when empty."""
    mappings_manager = MappingsManager(fmu_dir)
    renaming_table_relative_path = Path("data/custom/pdm_rms.renaming_table")
    renaming_table_path = fmu_dir.base_path / renaming_table_relative_path
    renaming_table_path.parent.mkdir(parents=True, exist_ok=True)
    renaming_table_path.write_text("existing renaming table\n", encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="No PDM-to-RMS primary wellbore mappings available",
    ):
        mappings_manager.write_pdm_rms_renaming_table(
            WellboreMappings(
                root=[
                    make_wellbore_identifier_mapping(
                        source_system=DataSystem.pdm,
                        target_system=DataSystem.simulator,
                        source_id="30/9-B-43 A",
                        target_id="B43A",
                    ),
                    make_wellbore_identifier_mapping(
                        source_system=DataSystem.smda,
                        target_system=DataSystem.rms,
                        source_id="NO 30/9-B-21 C",
                        target_id="30_9-B-21_C",
                    ),
                ]
            ),
            renaming_table_relative_path=renaming_table_relative_path,
        )

    assert renaming_table_path.read_text(encoding="utf-8") == (
        "existing renaming table\n"
    )


@pytest.mark.parametrize(
    ("method_name", "path_argument_name", "relative_path", "expected_error"),
    [
        (
            "write_rms_eclipse_csv",
            "csv_relative_path",
            Path("../outside.csv"),
            "csv_relative_path must stay within the project root",
        ),
        (
            "write_rms_eclipse_csv",
            "csv_relative_path",
            Path("/tmp/outside.csv"),
            "csv_relative_path must stay within the project root",
        ),
        (
            "write_rms_eclipse_renaming_table",
            "renaming_table_relative_path",
            Path("../outside.renaming_table"),
            "renaming_table_relative_path must stay within the project root",
        ),
        (
            "write_rms_eclipse_renaming_table",
            "renaming_table_relative_path",
            Path("/tmp/outside.renaming_table"),
            "renaming_table_relative_path must stay within the project root",
        ),
        (
            "write_pdm_rms_renaming_table",
            "renaming_table_relative_path",
            Path("../outside.renaming_table"),
            "renaming_table_relative_path must stay within the project root",
        ),
        (
            "write_pdm_rms_renaming_table",
            "renaming_table_relative_path",
            Path("/tmp/outside.renaming_table"),
            "renaming_table_relative_path must stay within the project root",
        ),
    ],
)
def test_write_methods_raise_for_paths_outside_project_root(
    fmu_dir: ProjectFMUDirectory,
    method_name: str,
    path_argument_name: str,
    relative_path: Path,
    expected_error: str,
) -> None:
    """Write paths must stay within the project root."""
    mappings_manager = MappingsManager(fmu_dir)
    method = getattr(mappings_manager, method_name)

    with pytest.raises(ValueError, match=expected_error):
        method(
            WellboreMappings(root=[make_wellbore_identifier_mapping()]),
            **{path_argument_name: relative_path},
        )


def test_mappings_manager_diff(
    fmu_dir: ProjectFMUDirectory,
    extra_fmu_dir: ProjectFMUDirectory,
    stratigraphy_mappings: StratigraphyMappings,
) -> None:
    """Tests that the mappings diff equals the mappings from the incoming resource."""
    mappings_manager: MappingsManager = MappingsManager(fmu_dir)
    mappings_manager.update_stratigraphy_mappings(stratigraphy_mappings)

    new_mappings_manager: MappingsManager = MappingsManager(extra_fmu_dir)
    new_mapping = StratigraphyIdentifierMapping(
        source_system=DataSystem.rms,
        target_system=DataSystem.smda,
        relation_type=RelationType.primary,
        source_id="TopViking",
        target_id="VIKING GP. Top",
    )
    new_mappings_manager.update_stratigraphy_mappings(
        StratigraphyMappings(root=[new_mapping])
    )

    diff = mappings_manager.get_mappings_diff(new_mappings_manager)

    assert len(diff.stratigraphy) == 1
    assert diff.stratigraphy == new_mappings_manager.load().stratigraphy


def test_mappings_manager_diff_mappings_raises(
    fmu_dir: ProjectFMUDirectory,
    extra_fmu_dir: ProjectFMUDirectory,
    stratigraphy_mappings: StratigraphyMappings,
) -> None:
    """Exception is raised when any of the mappings resources to diff does not exist.

    When trying to diff two mapping resources, the mappings file must
    exist in both directories in order to make a diff.
    """
    mappings_manager: MappingsManager = MappingsManager(fmu_dir)
    new_mappings_manager: MappingsManager = MappingsManager(extra_fmu_dir)

    expected_exp = (
        "Mappings resources to diff must exist in both directories: "
        "Current mappings resource exists: {}. "
        "Incoming mappings resource exists: {}."
    )

    with pytest.raises(FileNotFoundError, match=expected_exp.format("False", "False")):
        mappings_manager.get_mappings_diff(new_mappings_manager)

    mappings_manager.update_stratigraphy_mappings(stratigraphy_mappings)

    with pytest.raises(FileNotFoundError, match=expected_exp.format("True", "False")):
        mappings_manager.get_mappings_diff(new_mappings_manager)

    with pytest.raises(FileNotFoundError, match=expected_exp.format("False", "True")):
        new_mappings_manager.get_mappings_diff(mappings_manager)

    new_mappings_manager.update_stratigraphy_mappings(stratigraphy_mappings)
    assert mappings_manager.get_mappings_diff(new_mappings_manager)


def test_mappings_manager_merge_mappings(
    fmu_dir: ProjectFMUDirectory,
    extra_fmu_dir: ProjectFMUDirectory,
    stratigraphy_mappings: StratigraphyMappings,
    wellbore_mappings: WellboreMappings,
) -> None:
    """Tests that mappings from the incoming resource will overwrite current mappings.

    The current resource should be updated with all the mappings
    from the incoming resource.
    """
    mappings_manager: MappingsManager = MappingsManager(fmu_dir)
    mappings_manager.update_stratigraphy_mappings(stratigraphy_mappings)
    assert mappings_manager.stratigraphy_mappings == stratigraphy_mappings

    new_mappings_manager: MappingsManager = MappingsManager(extra_fmu_dir)
    new_mappings_manager.update_stratigraphy_mappings(StratigraphyMappings(root=[]))

    updated_mappings = mappings_manager.merge_mappings(new_mappings_manager)

    assert len(updated_mappings.stratigraphy) == 0
    assert updated_mappings.stratigraphy == mappings_manager.stratigraphy_mappings
    assert len(updated_mappings.wellbore) == 0

    mappings_manager.update_stratigraphy_mappings(stratigraphy_mappings)
    expected_no_of_mappings = 3
    assert len(mappings_manager.stratigraphy_mappings) == expected_no_of_mappings

    new_mapping = StratigraphyIdentifierMapping(
        source_system=DataSystem.rms,
        target_system=DataSystem.smda,
        relation_type=RelationType.primary,
        source_id="TopViking",
        target_id="VIKING GP. Top",
    )
    new_mappings_manager.update_stratigraphy_mappings(
        StratigraphyMappings(root=[new_mapping])
    )
    assert len(new_mappings_manager.stratigraphy_mappings) == 1

    updated_mappings = mappings_manager.merge_mappings(new_mappings_manager)

    assert len(updated_mappings.stratigraphy) == 1
    assert updated_mappings.stratigraphy == mappings_manager.stratigraphy_mappings
    assert (
        mappings_manager.stratigraphy_mappings
        == new_mappings_manager.stratigraphy_mappings
    )

    new_mappings_manager.update_wellbore_mappings(wellbore_mappings)
    updated_mappings = mappings_manager.merge_mappings(new_mappings_manager)
    assert updated_mappings.wellbore == mappings_manager.wellbore_mappings
    assert mappings_manager.wellbore_mappings == new_mappings_manager.wellbore_mappings
    assert len(updated_mappings.wellbore) == 1


def test_mappings_manager_merge_changes(
    fmu_dir: ProjectFMUDirectory,
    stratigraphy_mappings: StratigraphyMappings,
    wellbore_mappings: WellboreMappings,
) -> None:
    """Tests that mappings from the change object will overwrite current mappings.

    The current resource should be updated with all the mappings
    from the change object.
    """
    mappings_manager: MappingsManager = MappingsManager(fmu_dir)
    mappings_manager.update_stratigraphy_mappings(stratigraphy_mappings)
    assert mappings_manager.stratigraphy_mappings == stratigraphy_mappings

    # Assert empty change object overwrites current mappings
    change_object = Mappings()
    updated_mappings = mappings_manager.merge_changes(change_object)
    assert updated_mappings.stratigraphy == mappings_manager.stratigraphy_mappings
    assert len(mappings_manager.stratigraphy_mappings) == 0
    assert len(mappings_manager.wellbore_mappings) == 0

    new_mappings = StratigraphyMappings(
        root=[
            StratigraphyIdentifierMapping(
                source_system=DataSystem.rms,
                target_system=DataSystem.smda,
                relation_type=RelationType.primary,
                source_id="TopViking",
                target_id="VIKING GP. Top",
            )
        ]
    )

    # Assert change object overwrites current mappings
    change_object.stratigraphy = new_mappings
    updated_mappings = mappings_manager.merge_changes(change_object)

    assert len(updated_mappings.wellbore) == 0
    assert len(updated_mappings.stratigraphy) == 1
    assert updated_mappings.stratigraphy == new_mappings
    assert mappings_manager.stratigraphy_mappings == new_mappings

    change_object.wellbore = wellbore_mappings
    updated_mappings = mappings_manager.merge_changes(change_object)
    assert updated_mappings.wellbore == wellbore_mappings
    assert mappings_manager.wellbore_mappings == wellbore_mappings
    assert len(updated_mappings.wellbore) == 1


def test_mappings_manager_structured_diff_uses_full_item_identity(
    fmu_dir: ProjectFMUDirectory,
    stratigraphy_mappings: StratigraphyMappings,
) -> None:
    """Tests stratigraphy list changes are returned as added/removed with __full__."""
    mappings_manager = MappingsManager(fmu_dir)

    replacement_mapping = StratigraphyIdentifierMapping(
        source_system=DataSystem.rms,
        target_system=DataSystem.smda,
        relation_type=RelationType.primary,
        source_id="TopViking",
        target_id="VIKING GP. Top",
    )

    current_model = Mappings(stratigraphy=stratigraphy_mappings)
    incoming_model = Mappings(
        stratigraphy=StratigraphyMappings(
            root=[
                stratigraphy_mappings[0],
                stratigraphy_mappings[2],
                replacement_mapping,
            ]
        )
    )

    model_diff = mappings_manager.get_structured_model_diff(
        current_model, incoming_model
    )

    assert len(model_diff) == 1
    diff = model_diff[0]
    assert isinstance(diff, ListFieldDiff)
    assert diff.field_path == "stratigraphy.root"
    assert len(diff.added) == 1
    assert len(diff.removed) == 1
    assert diff.updated == []
    assert diff.added[0]["source_id"] == "TopViking"
    assert diff.removed[0]["source_id"] == "TopVOLANTIS"


def test_build_global_config_stratigraphy_empty(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Empty stratigraphy when no mappings and no RMS config."""
    mappings_manager = MappingsManager(fmu_dir)
    strat = mappings_manager.build_global_config_stratigraphy()
    assert strat.model_dump() == {}


def test_build_global_config_stratigraphy_only_rms(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """All entries are non-stratigraphic when there are no mappings."""
    fmu_dir.update_config(
        {
            "rms": {
                "path": "rms/model/test.rms15.0.1.0",
                "version": "15.0.1.0",
                "horizons": [
                    {"name": "MSL", "type": "interpreted"},
                    {"name": "TopX", "type": "interpreted"},
                ],
                "zones": [
                    {
                        "name": "Above",
                        "top_horizon_name": "MSL",
                        "base_horizon_name": "TopX",
                    }
                ],
            }
        }
    )

    mappings_manager = MappingsManager(fmu_dir)
    strat = mappings_manager.build_global_config_stratigraphy()

    result = strat.model_dump(mode="json", exclude_none=True, exclude_unset=True)
    for name in ("MSL", "TopX", "Above"):
        assert result[name] == {"stratigraphic": False, "name": name}
    assert len(result) == 3  # noqa: PLR2004


def test_build_global_config_stratigraphy_handles_optional_rms_lists(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Missing RMS horizons and zones should be treated as empty lists."""
    fmu_dir.update_config(
        {
            "rms": {
                "path": "rms/model/test.rms15.0.1.0",
                "version": "15.0.1.0",
            }
        }
    )

    mappings_manager = MappingsManager(fmu_dir)
    strat = mappings_manager.build_global_config_stratigraphy()

    assert strat.model_dump() == {}


def test_build_global_config_stratigraphy_only_mappings(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Only stratigraphic entries when there is no RMS config."""
    mappings_manager = MappingsManager(fmu_dir)
    mappings_manager.update_stratigraphy_mappings(
        StratigraphyMappings(
            root=[
                StratigraphyIdentifierMapping(
                    source_system=DataSystem.rms,
                    target_system=DataSystem.smda,
                    relation_type=RelationType.primary,
                    source_id="TopX",
                    target_id="X Fm. Top",
                ),
            ]
        )
    )

    strat = mappings_manager.build_global_config_stratigraphy()

    result = strat.model_dump(mode="json", exclude_none=True, exclude_unset=True)
    assert result == {"TopX": {"stratigraphic": True, "name": "X Fm. Top"}}


def test_build_global_config_stratigraphy_mapped_horizon_not_duplicated(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """A horizon with a primary mapping appears once as stratigraphic, not twice."""
    fmu_dir.update_config(
        {
            "rms": {
                "path": "rms/model/test.rms15.0.1.0",
                "version": "15.0.1.0",
                "horizons": [
                    {"name": "TopX", "type": "interpreted"},
                    {"name": "MSL", "type": "interpreted"},
                ],
                "zones": [],
            }
        }
    )
    mappings_manager = MappingsManager(fmu_dir)
    mappings_manager.update_stratigraphy_mappings(
        StratigraphyMappings(
            root=[
                StratigraphyIdentifierMapping(
                    source_system=DataSystem.rms,
                    target_system=DataSystem.smda,
                    relation_type=RelationType.primary,
                    source_id="TopX",
                    target_id="X Fm. Top",
                ),
            ]
        )
    )

    strat = mappings_manager.build_global_config_stratigraphy()

    result = strat.model_dump(mode="json", exclude_none=True, exclude_unset=True)
    assert result["TopX"] == {"stratigraphic": True, "name": "X Fm. Top"}
    assert result["MSL"] == {"stratigraphic": False, "name": "MSL"}
    assert len(result) == 2  # noqa: PLR2004


def test_build_global_config_stratigraphy_equivalent_with_primary_keeps_primary_entry(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Equivalent mappings should not change the matching primary entry."""
    mappings_manager = MappingsManager(fmu_dir)
    mappings_manager.update_stratigraphy_mappings(
        StratigraphyMappings(
            root=[
                StratigraphyIdentifierMapping(
                    source_system=DataSystem.rms,
                    target_system=DataSystem.smda,
                    relation_type=RelationType.primary,
                    source_id="TopX",
                    target_id="X Fm. Top",
                ),
                StratigraphyIdentifierMapping(
                    source_system=DataSystem.rms,
                    target_system=DataSystem.smda,
                    relation_type=RelationType.equivalent,
                    source_id="X Fm. Top",
                    target_id="X Fm. Top",
                ),
            ]
        )
    )

    strat = mappings_manager.build_global_config_stratigraphy()

    result = strat.model_dump(mode="json", exclude_none=True, exclude_unset=True)
    assert result == {"TopX": {"stratigraphic": True, "name": "X Fm. Top"}}


def test_build_global_config_stratigraphy_equivalent_only_mapping_is_kept(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Equivalent-only mappings should still yield a stratigraphic entry."""
    mappings_manager = MappingsManager(fmu_dir)
    mappings_manager.update_stratigraphy_mappings(
        StratigraphyMappings(
            root=[
                StratigraphyIdentifierMapping(
                    source_system=DataSystem.rms,
                    target_system=DataSystem.smda,
                    relation_type=RelationType.equivalent,
                    source_id="X Fm. Top",
                    target_id="X Fm. Top",
                ),
            ]
        )
    )

    strat = mappings_manager.build_global_config_stratigraphy()

    result = strat.model_dump(mode="json", exclude_none=True, exclude_unset=True)
    assert result == {
        "X Fm. Top": {
            "stratigraphic": True,
            "name": "X Fm. Top",
        }
    }


def test_build_global_config_stratigraphy_correct_drogon_integration(
    drogon_fmu_dir: ProjectFMUDirectory,
) -> None:
    """Drogon global config stratigraphy reconstructed from mappings and RMS."""
    stratigraphy = drogon_fmu_dir._mappings.build_global_config_stratigraphy()
    assert (
        stratigraphy.model_dump(mode="json", exclude_none=True, exclude_unset=True)
        == GLOBAL_CONFIG_STRATIGRAPHY
    )
