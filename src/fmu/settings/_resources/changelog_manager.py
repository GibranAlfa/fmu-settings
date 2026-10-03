from __future__ import annotations

import os
import socket
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

from fmu.settings._resources.log_manager import LogManager
from fmu.settings.models._enums import ChangeType, FilterType
from fmu.settings.models.change_info import ChangeInfo
from fmu.settings.models.diff import ListFieldDiff, ResourceDiff
from fmu.settings.models.log import Filter, Log, LogFileName

if TYPE_CHECKING:
    # Avoid circular dependency for type hint in __init__ only
    from fmu.settings._fmu_dir import (
        ProjectFMUDirectory,
    )


class ChangelogManager(LogManager[ChangeInfo]):
    """Manages the .fmu changelog file."""

    fmu_dir: ProjectFMUDirectory

    def __init__(self: Self, fmu_dir: ProjectFMUDirectory) -> None:
        """Initializes the Change log resource manager."""
        super().__init__(fmu_dir, Log[ChangeInfo])

    @property
    def relative_path(self: Self) -> Path:
        """Returns the relative path to the log file."""
        return Path("logs") / LogFileName.changelog

    def log_update_to_changelog(
        self: Self,
        updates: dict[str, Any],
        old_resource_dict: dict[str, Any],
        relative_path: Path,
        *,
        structured_diff: list[ResourceDiff] | None = None,
    ) -> None:
        """Log descriptions and per-key differences after a resource update.

        None means no structured comparison was supplied. An empty list means
        the comparison found no value changes. Overlapping update keys receive
        each difference once, under the most specific matching key.
        """
        grouped_diffs = self._group_update_diffs(updates, structured_diff)
        missing = object()
        for key in updates:
            old_value = self._get_dot_notation_key(old_resource_dict, key, missing)
            change_type = ChangeType.add if old_value is missing else ChangeType.update
            verb = "Added" if change_type == ChangeType.add else "Updated"
            change_entry = ChangeInfo(
                timestamp=datetime.now(UTC),
                change_type=change_type,
                user=os.getenv("USER", "unknown"),
                path=self.fmu_dir.path,
                change=f"{verb} field '{key}'.",
                structured_diff=grouped_diffs[key],
                hostname=socket.gethostname(),
                file=str(relative_path),
                key=key,
            )
            self.add_log_entry(change_entry)

    @staticmethod
    def _group_update_diffs(
        updates: dict[str, Any], differences: list[ResourceDiff] | None
    ) -> dict[str, list[ResourceDiff] | None]:
        """Assign differences to update keys without duplicating batch payloads."""
        grouped: dict[str, list[ResourceDiff] | None] = {
            key: None if differences is None else [] for key in updates
        }
        if differences is None or not updates:
            return grouped
        for diff in differences:
            if isinstance(diff, ListFieldDiff) and not (
                diff.added or diff.removed or diff.updated
            ):
                continue
            parents = [
                key
                for key in updates
                if diff.field_path == key or diff.field_path.startswith(f"{key}.")
            ]
            children = [key for key in updates if key.startswith(f"{diff.field_path}.")]
            if parents:
                key = max(parents, key=len)
            elif children:
                key = min(children, key=len)
            else:
                key = next(iter(updates))
            key_diffs = grouped[key]
            if key_diffs is not None:
                key_diffs.append(diff)
        return grouped

    def log_merge_to_changelog(
        self: Self, source_path: Path, incoming_path: Path, merged_resources: list[str]
    ) -> None:
        """Logs a change entry with merge details to the changelog."""
        resources_string = ", ".join([f"'{resource}'" for resource in merged_resources])
        change_string = (
            f"Merged resources {resources_string} from "
            f"'{incoming_path}' into '{source_path}'."
        )
        self.add_log_entry(
            ChangeInfo(
                timestamp=datetime.now(UTC),
                change_type=ChangeType.merge,
                user=os.getenv("USER", "unknown"),
                path=source_path,
                change=change_string,
                hostname=socket.gethostname(),
                file=resources_string,
                key=".fmu",
            )
        )

    def log_copy_revision_to_changelog(self: Self, source_path: Path) -> None:
        """Logs a change entry with revision copy details to the changelog."""
        self.add_log_entry(
            ChangeInfo(
                timestamp=datetime.now(UTC),
                change_type=ChangeType.copy,
                user=os.getenv("USER", "unknown"),
                path=source_path,
                change=f"Copied project revision from {source_path}.",
                hostname=socket.gethostname(),
                file="N/A",
                key="project_revision",
            )
        )

    def log_init_to_changelog(self: Self) -> None:
        """Logs a change entry indicating that the project was initialized."""
        self.add_log_entry(
            ChangeInfo(
                timestamp=datetime.now(UTC),
                change_type=ChangeType.init,
                user=os.getenv("USER", "unknown"),
                path=self.fmu_dir.path,
                change=f"Initialized .fmu directory at '{self.fmu_dir.path}'.",
                hostname=socket.gethostname(),
                file="N/A",
                key="project_initialization",
            )
        )

    def log_restore_to_changelog(self: Self, relative_path: Path, source: str) -> None:
        """Logs a change entry indicating that a resource was restored."""
        self.add_log_entry(
            ChangeInfo(
                timestamp=datetime.now(UTC),
                change_type=ChangeType.restore,
                user=os.getenv("USER", "unknown"),
                path=self.fmu_dir.path,
                change=f"Restored '{relative_path}' from {source}.",
                hostname=socket.gethostname(),
                file=str(relative_path),
                key=relative_path.stem,
            )
        )

    def _get_latest_change_timestamp(self: Self) -> datetime:
        """Get the timestamp of the latest change entry in the changelog."""
        return self.load()[-1].timestamp

    def get_changelog_diff(
        self: Self, incoming_changelog: ChangelogManager
    ) -> Log[ChangeInfo]:
        """Get new entries from the incoming changelog.

        All log entries from the incoming changelog newer than the
        log entries in the current changelog are returned.
        """
        if self.exists and incoming_changelog.exists:
            starting_point = self._get_latest_change_timestamp()
            return incoming_changelog.filter_log(
                Filter(
                    field_name="timestamp",
                    filter_value=str(starting_point),
                    filter_type=FilterType.date,
                    operator=">",
                )
            )
        raise FileNotFoundError(
            "Changelog resources to diff must exist in both directories: "
            f"Current changelog resource exists: {self.exists}. "
            f"Incoming changelog resource exists: {incoming_changelog.exists}."
        )

    def merge_changelog(
        self: Self, incoming_changelog: ChangelogManager
    ) -> Log[ChangeInfo]:
        """Add new entries from the incoming changelog to the current changelog.

        All log entries from the incoming changelog newer than the
        log entries in the current changelog are added.
        """
        new_log_entries = self.get_changelog_diff(incoming_changelog)
        return self.merge_changes(new_log_entries.root)

    def merge_changes(self: Self, change: list[ChangeInfo]) -> Log[ChangeInfo]:
        """Merge a list of changes into the current changelog.

        All log entries in the change object are added to the changelog.
        """
        for entry in change:
            self.add_log_entry(entry)
        return self.load()
