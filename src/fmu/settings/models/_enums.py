"""Contains enumerations used in this package."""

from enum import StrEnum


class ChangeType(StrEnum):
    """The types of change that can be made on a file."""

    update = "update"
    remove = "remove"
    add = "add"
    reset = "reset"
    merge = "merge"
    copy = "copy"


class FilterType(StrEnum):
    """The supported types to filter on."""

    date = "date"
    number = "number"
    text = "text"


class CacheResource(StrEnum):
    """Resources that can be cached and restored."""

    config = "config.json"
    mappings = "mappings.json"
