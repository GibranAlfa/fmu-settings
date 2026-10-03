"""Model for the log entries in the the changelog file."""

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from pydantic import AwareDatetime, BaseModel, Field, field_validator

from fmu.settings.models._enums import ChangeType
from fmu.settings.models.diff import ResourceDiff


class ChangeInfo(BaseModel):
    """Represents a change in the changelog file."""

    timestamp: AwareDatetime = Field(
        default_factory=lambda: datetime.now(UTC), strict=True
    )
    change_type: ChangeType
    user: str
    path: Path
    change: str
    structured_diff: list[ResourceDiff] | None = None
    hostname: str
    file: str
    key: str

    @field_validator("timestamp", mode="before")
    @classmethod
    def convert_timestamp(cls, value: str) -> AwareDatetime:
        """Convert timestamp values given as a 'str' or Pandas 'Timestamp'.

        Values of other types will be handled by Pydantic.
        """
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        if isinstance(value, pd.Timestamp):
            return value.to_pydatetime()
        return value
