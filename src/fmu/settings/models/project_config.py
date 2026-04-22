"""The model for config.json."""

import getpass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, Field

from fmu.datamodels.common.access import Access
from fmu.datamodels.common.masterdata import Masterdata
from fmu.datamodels.fmu_results.fields import Model
from fmu.settings import __version__
from fmu.settings.types import ResettableBaseModel, VersionStr  # noqa: TC001


class RmsCoordinateSystem(BaseModel):
    """The project coordinate system of an RMS project."""

    name: str
    """Name of the coordinate system."""


class RmsStratigraphicZone(BaseModel):
    """A stratigraphic zone from an RMS project."""

    name: str
    """Name of the zone."""

    top_horizon_name: str
    """Name of the horizon at the top of the zone."""

    base_horizon_name: str
    """Name of the horizon at the base of the zone."""

    stratigraphic_column_name: list[str] | None = None
    """Name of the stratigraphic column the zone belongs to."""


class RmsHorizon(BaseModel):
    """A horizon from an RMS project."""

    name: str
    """Name of the horizon."""

    type: Literal[
        "calculated",
        "calculated_unconformity",
        "interpreted",
        "interpreted_unconformity",
        "interpreted_intrusion",
    ]
    """Type of the horizon."""


class RmsWell(BaseModel):
    """A well from an RMS project with added metadata."""

    name: str
    """Name of the well."""

    planned: bool = False
    """Whether the well is planned."""


class RmsProject(BaseModel):
    """RMS project configuration."""

    path: Path
    version: str
    coordinate_system: RmsCoordinateSystem | None = None
    zones: list[RmsStratigraphicZone] | None = None
    horizons: list[RmsHorizon] | None = None
    wells: list[RmsWell] | None = None


class ProjectConfig(ResettableBaseModel):
    """The configuration file in a .fmu directory.

    Stored as config.json.
    """

    version: VersionStr
    created_at: AwareDatetime
    created_by: str
    last_modified_at: AwareDatetime | None = None
    last_modified_by: str | None = None
    masterdata: Masterdata | None = None
    model: Model | None = None
    access: Access | None = None
    cache_max_revisions: int = Field(default=5, ge=5)
    rms: RmsProject | None = None

    @classmethod
    def reset(cls: type[Self]) -> Self:
        """Resets the configuration to defaults.

        Returns:
            The new default Config object
        """
        return cls(
            version=__version__,
            created_at=datetime.now(UTC),
            created_by=getpass.getuser(),
            last_modified_at=None,
            last_modified_by=None,
            masterdata=None,
            model=None,
            access=None,
            cache_max_revisions=5,
            rms=None,
        )
