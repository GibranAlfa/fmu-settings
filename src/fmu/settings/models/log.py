"""Module for the log file and related models."""

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, Self, TypeVar

from pydantic import BaseModel, Field, RootModel

from fmu.settings.models._enums import FilterType

LogEntryType = TypeVar("LogEntryType", bound=BaseModel)


class Log(RootModel[list[LogEntryType]]):
    """Represents a log file in a .fmu directory."""

    root: list[LogEntryType] = Field(default_factory=list)

    def add_entry(self: Self, entry: LogEntryType) -> None:
        """Adds a log entry to the log."""
        self.root.append(entry)

    def __getitem__(self: Self, index: int) -> LogEntryType:
        """Retrieves a log entry from the log using the specified index."""
        return self.root[index]

    def __iter__(self: Self) -> Any:
        """Returns an iterator for the log."""
        return iter(self.root)

    def __len__(self: Self) -> int:
        """Returns the number of log entries in the log."""
        return len(self.root)


class Filter(BaseModel):
    """Represents a filter that can be applied on a log file."""

    field_name: str
    filter_value: str
    filter_type: FilterType
    operator: Literal[">=", "<=", "==", "!="]

    def parse_filter_value(self: Self) -> str | datetime | int:
        """Parse filter value to its type."""
        match self.filter_type:
            case FilterType.date:
                return datetime.fromisoformat(self.filter_value)
            case FilterType.number:
                return int(self.filter_value)
            case FilterType.text:
                return self.filter_value
            case _:
                raise ValueError(
                    "Invalid filter type supplied when parsing filter value."
                )


class LogFileName(StrEnum):
    """The log files in the .fmu directory."""

    changelog = "changelog.json"
