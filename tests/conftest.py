"""Root configuration for pytest."""

import stat
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
import yaml
from fmu.datamodels import (
    Asset,
    CoordinateSystem,
    CountryItem,
    DiscoveryItem,
    FieldItem,
    Masterdata,
    Smda,
    StratigraphicColumn,
)
from fmu.datamodels.common.enums import Classification
from fmu.datamodels.fmu_results import fields
from fmu.datamodels.fmu_results.global_configuration import (
    Access,
    GlobalConfiguration,
    Stratigraphy,
    StratigraphyElement,
)
from pytest import MonkeyPatch

from fmu.settings._drogon import (
    ACCESS,
    GLOBAL_CONFIG_STRATIGRAPHY,
    MASTERDATA,
    MODEL,
    RMS_COORDINATE_SYSTEM,
    RMS_HORIZONS,
    RMS_WELLS,
    RMS_ZONES,
    STRATIGRAPHY_MAPPINGS,
    create_drogon_fmu_dir,
)
from fmu.settings._fmu_dir import ProjectFMUDirectory, UserFMUDirectory
from fmu.settings._init import (
    REQUIRED_FMU_PROJECT_SUBDIRS,
    init_fmu_directory,
    init_user_fmu_directory,
)
from fmu.settings._version import __version__
from fmu.settings.models.project_config import ProjectConfig
from fmu.settings.models.user_config import UserConfig


@pytest.fixture
def no_permissions() -> Callable[[str | Path], AbstractContextManager[None]]:
    """Returns a context manager to remove user permissions on a path."""

    @contextmanager
    def ctx_manager(filepath: str | Path) -> Iterator[None]:
        path = Path(filepath)
        path.chmod(stat.S_IRUSR)
        yield
        path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

    return ctx_manager


@pytest.fixture
def unix_epoch_utc() -> datetime:
    """Returns a fixed datetime used in testing."""
    return datetime(1970, 1, 1, 0, 0, tzinfo=UTC)


@pytest.fixture
def fmu_project_root(tmp_path: Path) -> Path:
    """Create the minimum directory layout for an FMU project root."""
    for dir in REQUIRED_FMU_PROJECT_SUBDIRS:
        (tmp_path / dir).mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def config_dict(unix_epoch_utc: datetime) -> dict[str, Any]:
    """A dictionary representing a .fmu config."""
    return {
        "version": __version__,
        "created_at": unix_epoch_utc,
        "created_by": "user",
        "last_modified_at": unix_epoch_utc,
        "last_modified_by": "user",
        "cache_max_revisions": 5,
        "masterdata": None,
        "model": None,
        "access": None,
        "rms": None,
    }


@pytest.fixture
def masterdata_dict() -> dict[str, Any]:
    """Example masterdata from SMDA."""
    return deepcopy(MASTERDATA)


@pytest.fixture
def model_dict() -> dict[str, Any]:
    """Example model information."""
    return deepcopy(MODEL)


@pytest.fixture
def access_dict() -> dict[str, Any]:
    """Example access information."""
    return deepcopy(ACCESS)


@pytest.fixture
def stratigraphy_dict() -> dict[str, Any]:
    """Example global configuration stratigraphy information."""
    return deepcopy(GLOBAL_CONFIG_STRATIGRAPHY)


@pytest.fixture
def stratigraphy_mappings_list() -> list[dict[str, Any]]:
    """Example stratigraphy mapping information."""
    return deepcopy(STRATIGRAPHY_MAPPINGS)


@pytest.fixture
def rms_zones_list() -> list[dict[str, Any]]:
    """Example RMS zones list."""
    return deepcopy(RMS_ZONES)


@pytest.fixture
def rms_horizons_list() -> list[dict[str, Any]]:
    """Example RMS horizons list."""
    return deepcopy(RMS_HORIZONS)


@pytest.fixture
def rms_wells_list() -> list[dict[str, str | bool]]:
    """Example RMS wells list."""
    return deepcopy(RMS_WELLS)


@pytest.fixture
def rms_coordinate_system() -> dict[str, str]:
    """Example RMS coordinate system."""
    return deepcopy(RMS_COORDINATE_SYSTEM)


@pytest.fixture
def global_variables_without_masterdata() -> dict[str, Any]:
    """Example global_variables.yml file without masterdata."""
    return {
        "global": {
            "dates": ["2018-01-01", "2018-07-01", "2019-07-01", "2020-07-01"],
        },
    }


@pytest.fixture
def global_variables_with_masterdata(
    masterdata_dict: dict[str, Any],
    access_dict: dict[str, Any],
    model_dict: dict[str, Any],
    stratigraphy_dict: dict[str, Any],
    global_variables_without_masterdata: dict[str, Any],
) -> dict[str, Any]:
    """Example global_variables.yml file with masterdata."""
    return {
        "masterdata": masterdata_dict,
        "access": access_dict,
        "model": model_dict,
        "stratigraphy": stratigraphy_dict,
        **global_variables_without_masterdata,
    }


@pytest.fixture
def fmuconfig_with_input(  # noqa: PLR0913 too many args
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    masterdata_dict: dict[str, Any],
    access_dict: dict[str, Any],
    model_dict: dict[str, Any],
    stratigraphy_dict: dict[str, Any],
    global_variables_without_masterdata: dict[str, Any],
) -> Path:
    """Creates an fmuconfig/ path and input directory.

    Returns:
        tmp_path.
    """
    fmuconfig_input = tmp_path / "fmuconfig/input"
    fmuconfig_input.mkdir(parents=True, exist_ok=True)

    with open(fmuconfig_input / "_masterdata.yml", "w") as f:
        yaml.safe_dump(masterdata_dict, f)
    with open(fmuconfig_input / "_access.yml", "w") as f:
        yaml.safe_dump(access_dict, f)
    with open(fmuconfig_input / "_stratigraphy.yml", "w") as f:
        yaml.safe_dump(stratigraphy_dict, f)

    global_config_dict = {
        **global_variables_without_masterdata,
        "model": model_dict,
        "masterdata": "!include _masterdata.yml",
        "access": "!include _access.yml",
        "stratigraphy": "!include _stratigraphy.yml",
    }
    # Remove quotes around strings. PyYAML quotes string beginning with ! by default as
    # they indicate a yaml tag, for which fmu-config has defined one in this case.
    global_config_yml = yaml.dump(
        global_config_dict, default_style=None, default_flow_style=False
    ).replace("'", "")

    with open(fmuconfig_input / "global_master_config.yml", "w") as f:
        f.write(global_config_yml)

    return tmp_path


@pytest.fixture
def fmuconfig_with_output(  # noqa: PLR0913 too many args
    fmuconfig_with_input: Path,
    global_variables_with_masterdata: dict[str, Any],
) -> Path:
    """Creates an fmuconfig/ path and input/output directory.

    Returns:
        tmp_path
    """
    fmuconfig_output = fmuconfig_with_input / "fmuconfig/output"
    fmuconfig_output.mkdir(parents=True, exist_ok=True)

    with open(fmuconfig_output / "global_variables.yml", "w") as f:
        yaml.safe_dump(
            global_variables_with_masterdata,
            f,
            default_style=None,
            default_flow_style=False,
        )

    return fmuconfig_with_input


@pytest.fixture
def generate_strict_valid_globalconfiguration() -> Callable[[], GlobalConfiguration]:
    """Generates a global configuration that is valid, but can switch particular models.

    Required country and field lists get minimal valid defaults.
    """

    def _generate_cfg(  # noqa: PLR0913
        *,
        classification: Classification | None = Classification.internal,
        asset: Asset | None = None,
        coordinate_system: CoordinateSystem | None = None,
        stratigraphic_column: StratigraphicColumn | None = None,
        country_items: list[CountryItem] | None = None,
        discovery_items: list[DiscoveryItem] | None = None,
        field_items: list[FieldItem] | None = None,
        model: fields.Model | None = None,
    ) -> GlobalConfiguration:
        if country_items is None:
            country_items = [CountryItem(identifier="default_country", uuid=uuid4())]
        if field_items is None:
            field_items = [FieldItem(identifier="default_field", uuid=uuid4())]

        return GlobalConfiguration(
            access=Access(asset=asset or Asset(name=""), classification=classification),
            masterdata=Masterdata(
                smda=Smda(
                    coordinate_system=(
                        coordinate_system
                        or CoordinateSystem(identifier="", uuid=uuid4())
                    ),
                    stratigraphic_column=(
                        stratigraphic_column
                        or StratigraphicColumn(identifier="", uuid=uuid4())
                    ),
                    country=country_items,
                    discovery=discovery_items or [],
                    field=field_items,
                )
            ),
            model=model or fields.Model(name="", revision=""),
            stratigraphy=Stratigraphy(
                {"MSL": StratigraphyElement(name="MSL", stratigraphic=False)}
            ),
        )

    return _generate_cfg


@pytest.fixture
def config_dict_with_masterdata(
    unix_epoch_utc: datetime,
    masterdata_dict: dict[str, Any],
    model_dict: dict[str, Any],
) -> dict[str, Any]:
    """A dictionary representing a .fmu config."""
    return {
        "version": __version__,
        "created_at": unix_epoch_utc,
        "created_by": "user",
        "last_modified_at": unix_epoch_utc,
        "last_modified_by": "user",
        "cache_max_revisions": 5,
        "masterdata": masterdata_dict,
        "model": model_dict,
    }


@pytest.fixture
def config_model(config_dict: dict[str, Any]) -> ProjectConfig:
    """A ProjectConfig model representing a .fmu config file."""
    return ProjectConfig.model_validate(config_dict)


@pytest.fixture
def config_model_with_masterdata(
    config_dict_with_masterdata: dict[str, Any],
) -> ProjectConfig:
    """A ProjectConfig model representing a .fmu config file."""
    return ProjectConfig.model_validate(config_dict_with_masterdata)


@pytest.fixture
def user_config_dict(unix_epoch_utc: datetime) -> dict[str, Any]:
    """A dictionary representing a .fmu user config."""
    return {
        "version": __version__,
        "created_at": unix_epoch_utc,
        "last_modified_at": unix_epoch_utc,
        "cache_max_revisions": 5,
        "user_api_keys": {
            "smda_subscription": None,
        },
        "recent_project_directories": [],
    }


@pytest.fixture
def user_config_model(user_config_dict: dict[str, Any]) -> UserConfig:
    """A UserConfig model representing a .fmu config file."""
    return UserConfig.model_validate(user_config_dict)


@pytest.fixture(scope="function")
def fmu_dir(fmu_project_root: Path, unix_epoch_utc: datetime) -> ProjectFMUDirectory:
    """Create an ProjectFMUDirectory instance for testing."""
    with (
        patch(
            "fmu.settings.models.project_config.getpass.getuser",
            return_value="user",
        ),
        patch(
            "fmu.settings._resources.config_managers.getpass.getuser",
            return_value="user",
        ),
        patch("fmu.settings.models.project_config.datetime") as mock_datetime,
        patch("fmu.settings._resources.config_managers.datetime") as mock_cm_datetime,
    ):
        mock_datetime.now.return_value = unix_epoch_utc
        mock_datetime.datetime.now.return_value = unix_epoch_utc
        mock_cm_datetime.now.return_value = unix_epoch_utc
        return init_fmu_directory(fmu_project_root)


@pytest.fixture(scope="function")
def drogon_fmu_dir(tmp_path: Path, unix_epoch_utc: datetime) -> ProjectFMUDirectory:
    """Create an ProjectFMUDirectory instance for testing."""
    with (
        patch(
            "fmu.settings.models.project_config.getpass.getuser",
            return_value="user",
        ),
        patch(
            "fmu.settings._resources.config_managers.getpass.getuser",
            return_value="user",
        ),
        patch("fmu.settings.models.project_config.datetime") as mock_datetime,
        patch("fmu.settings._resources.config_managers.datetime") as mock_cm_datetime,
    ):
        mock_datetime.now.return_value = unix_epoch_utc
        mock_datetime.datetime.now.return_value = unix_epoch_utc
        mock_cm_datetime.now.return_value = unix_epoch_utc
        return create_drogon_fmu_dir(tmp_path)


@pytest.fixture(scope="function")
def extra_fmu_dir(
    fmu_project_root: Path,
    unix_epoch_utc: datetime,
) -> ProjectFMUDirectory:
    """Create an extra ProjectFMUDirectory instance for testing of diff and sync."""
    extra_fmu_path = fmu_project_root / Path("extra_fmu")
    extra_fmu_path.mkdir(parents=True)
    for dir_name in REQUIRED_FMU_PROJECT_SUBDIRS:
        (extra_fmu_path / dir_name).mkdir(parents=True, exist_ok=True)
    with (
        patch(
            "fmu.settings.models.project_config.getpass.getuser",
            return_value="user",
        ),
        patch(
            "fmu.settings._resources.config_managers.getpass.getuser",
            return_value="user",
        ),
        patch("fmu.settings.models.project_config.datetime") as mock_datetime,
        patch("fmu.settings._resources.config_managers.datetime") as mock_cm_datetime,
    ):
        mock_datetime.now.return_value = unix_epoch_utc
        mock_datetime.datetime.now.return_value = unix_epoch_utc
        mock_cm_datetime.now.return_value = unix_epoch_utc
        return init_fmu_directory(extra_fmu_path)


@pytest.fixture
def user_fmu_dir(tmp_path: Path, unix_epoch_utc: datetime) -> UserFMUDirectory:
    """Create an ProjectFMUDirectory instance for testing."""
    with (
        patch("pathlib.Path.home", return_value=tmp_path),
        patch("fmu.settings.models.user_config.datetime") as mock_datetime,
        patch("fmu.settings._resources.config_managers.datetime") as mock_cm_datetime,
    ):
        mock_datetime.now.return_value = unix_epoch_utc
        mock_datetime.datetime.now.return_value = unix_epoch_utc
        mock_cm_datetime.now.return_value = unix_epoch_utc

        return init_user_fmu_directory()
