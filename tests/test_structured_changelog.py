"""Tests the persisted structured changelog contract."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import UUID

import pytest
from fmu.datamodels.context.mappings import DataSystem
from fmu.datamodels.fmu_results.fields import Model
from pydantic import BaseModel

from fmu.settings import ProjectFMUDirectory
from fmu.settings.models._enums import ChangeType, FilterType
from fmu.settings.models.change_info import ChangeInfo
from fmu.settings.models.diff import (
    ListFieldDiff,
    ListUpdatedEntry,
    ResourceDiff,
    ScalarFieldDiff,
)
from fmu.settings.models.log import Filter, Log
from fmu.settings.models.mappings import (
    InternalMappings,
    InternalRelationType,
    InternalWellboreIdentifierMapping,
    InternalWellboreMappings,
)


@pytest.fixture
def wellbore_mappings() -> InternalWellboreMappings:
    """A source mapped in its own system and to a simulator."""
    return InternalWellboreMappings(
        root=[
            InternalWellboreIdentifierMapping(
                source_system=DataSystem.rms,
                target_system=target,
                relation_type=InternalRelationType.primary,
                source_id="A",
                target_id=identifier,
            )
            for target, identifier in [
                (DataSystem.rms, "A"),
                (DataSystem.simulator, "B"),
            ]
        ]
    )


@pytest.mark.parametrize("method", ["set", "update"])
def test_config_diff_uses_saved_values(
    fmu_dir: ProjectFMUDirectory, method: str
) -> None:
    """Both update paths preserve the old model and omit metadata changes."""
    fmu_dir.config.update(
        {"model": Model(name="old", revision="1", description=["old text"])}
    )
    before = fmu_dir.config.load().model_copy(deep=True)
    value = {"name": "new", "revision": "1", "description": ["new text"]}
    if method == "set":
        fmu_dir.config.set("model", value)
    else:
        fmu_dir.config.update({"model": value})

    entry = fmu_dir.changelog.load(force=True)[-1]
    assert entry.key == "model"
    assert entry.change == "Updated field 'model'."
    assert entry.structured_diff == [
        ScalarFieldDiff(
            field_path="model.description", before=["old text"], after=["new text"]
        ),
        ScalarFieldDiff(field_path="model.name", before="old", after="new"),
    ]
    assert before.model is not None and before.model.name == "old"


def test_config_parent_child_updates_assign_each_diff_once(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """A child entry owns its diff even when the parent is updated too."""
    fmu_dir.config.update(
        {"model": Model(name="old", revision="1", description=["old text"])}
    )
    fmu_dir.config.update(
        {
            "model": {"name": "parent", "revision": "1", "description": ["new text"]},
            "model.name": "child",
        }
    )
    parent, child = list(fmu_dir.changelog.load(force=True))[-2:]
    assert parent.structured_diff == [
        ScalarFieldDiff(
            field_path="model.description", before=["old text"], after=["new text"]
        )
    ]
    assert child.structured_diff == [
        ScalarFieldDiff(field_path="model.name", before="old", after="child")
    ]


def test_config_null_and_noop_updates(fmu_dir: ProjectFMUDirectory) -> None:
    """Null remains a value, while an identical update has an empty diff."""
    fmu_dir.config.update({"model": Model(name="new", revision="1")})
    entry = fmu_dir.changelog.load()[-1]
    assert entry.change_type == ChangeType.update
    model = fmu_dir.config.load().model
    assert model is not None
    assert entry.structured_diff == [
        ScalarFieldDiff(
            field_path="model",
            before=None,
            after=model.model_dump(mode="json"),
        )
    ]
    fmu_dir.config.set("model", None)
    null_diffs = fmu_dir.changelog.load()[-1].structured_diff
    assert null_diffs is not None
    assert isinstance(null_diffs[0], ScalarFieldDiff)
    assert null_diffs[0].after is None
    fmu_dir.config.set("model", None)
    assert fmu_dir.changelog.load()[-1].structured_diff == []


@pytest.mark.parametrize("failure", ["validation", "save"])
def test_failed_update_has_no_success_entry(
    fmu_dir: ProjectFMUDirectory, failure: str
) -> None:
    """Failures before saving a resource do not append a changelog entry."""
    count = len(fmu_dir.changelog.load()) if fmu_dir.changelog.exists else 0
    if failure == "validation":
        with pytest.raises(ValueError):
            fmu_dir.config.set("cache_max_revisions", -1)
    else:
        with (
            patch.object(fmu_dir.config, "save", side_effect=PermissionError),
            pytest.raises(PermissionError),
        ):
            fmu_dir.config.set("cache_max_revisions", 5)
    assert not fmu_dir.changelog.exists or len(fmu_dir.changelog.load()) == count


@pytest.mark.parametrize("edit", ["target", "uuid", "unmappable"])
def test_mapping_target_edits_are_updates(
    fmu_dir: ProjectFMUDirectory,
    wellbore_mappings: InternalWellboreMappings,
    edit: str,
) -> None:
    """Target edits keep the source identity and preserve before values."""
    manager = fmu_dir.mappings
    manager.update_internal_wellbore_mappings(wellbore_mappings)
    changed = wellbore_mappings.model_copy(deep=True)
    cross_system = next(m for m in changed if m.source_system != m.target_system)
    old_target = cross_system.target_id
    if edit == "target":
        cross_system.target_id = "new target"
    elif edit == "uuid":
        cross_system.source_uuid = UUID(int=1)
        cross_system.target_uuid = UUID(int=2)
    else:
        cross_system.relation_type = InternalRelationType.unmappable
        cross_system.target_id = None
    manager.update_internal_wellbore_mappings(changed)
    entry = fmu_dir.changelog.load(force=True)[-1]
    assert entry.structured_diff is not None
    diff = entry.structured_diff[0]
    assert isinstance(diff, ListFieldDiff)
    assert diff.added == diff.removed == []
    assert len(diff.updated) == 1
    assert diff.updated[0].before["target_id"] == old_target
    assert diff.updated[0].after == cross_system.model_dump(mode="json")
    assert len(diff.updated[0].key) == 4
    assert cross_system.source_id == diff.updated[0].key[-1]
    manager.update_internal_wellbore_mappings(changed)
    assert fmu_dir.changelog.load()[-1].structured_diff == []
    manager.update_internal_wellbore_mappings(InternalWellboreMappings(root=[]))
    removal_diffs = fmu_dir.changelog.load()[-1].structured_diff
    assert removal_diffs is not None
    removal = removal_diffs[0]
    assert isinstance(removal, ListFieldDiff) and len(removal.removed) == len(changed)


def test_mapping_reorder_has_no_value_diff(
    fmu_dir: ProjectFMUDirectory, wellbore_mappings: InternalWellboreMappings
) -> None:
    """Mapping order is not part of the identity-based changelog comparison."""
    fmu_dir.mappings.update_internal_wellbore_mappings(wellbore_mappings)
    fmu_dir.mappings.update_internal_wellbore_mappings(
        InternalWellboreMappings(root=list(reversed(wellbore_mappings.root)))
    )
    assert fmu_dir.changelog.load()[-1].structured_diff == []


def test_mapping_source_rename_is_remove_and_add(
    fmu_dir: ProjectFMUDirectory, wellbore_mappings: InternalWellboreMappings
) -> None:
    """Renames change identity without pairing unrelated source mappings."""
    renamed = wellbore_mappings.model_copy(deep=True)
    for item in renamed:
        item.source_id = "new source"
        if item.source_system == item.target_system:
            item.target_id = "new source"
    differences = fmu_dir.mappings.get_structured_model_diff(
        InternalMappings(wellbore=wellbore_mappings), InternalMappings(wellbore=renamed)
    )
    assert len(differences) == 1
    diff = differences[0]
    assert isinstance(diff, ListFieldDiff)
    assert len(diff.added) == len(diff.removed) == 2
    assert not diff.updated


def test_metadata_only_update_has_empty_diff(fmu_dir: ProjectFMUDirectory) -> None:
    """Ignored metadata cannot turn a no-op into a value change."""
    fmu_dir.config.set("created_by", "another user")
    assert fmu_dir.changelog.load()[-1].structured_diff == []


def test_diff_grouping_respects_path_boundaries(fmu_dir: ProjectFMUDirectory) -> None:
    """Similarly named fields and root-model descendants receive separate diffs."""
    name_diff = ScalarFieldDiff(field_path="model.name", before="old", after="new")
    named_diff = ScalarFieldDiff(field_path="model.names", before=[], after=["new"])
    list_diff = ListFieldDiff(
        field_path="stratigraphy.root",
        added=[{"source_id": "A"}],
        removed=[],
        updated=[],
    )
    fmu_dir.changelog.log_update_to_changelog(
        {"model.name": "new", "model.names": ["new"], "stratigraphy": []},
        {"model": {"name": "old", "names": []}, "stratigraphy": []},
        Path("config.json"),
        structured_diff=[name_diff, named_diff, list_diff],
    )
    entries = fmu_dir.changelog.load(force=True)
    assert [entry.structured_diff for entry in entries] == [
        [name_diff],
        [named_diff],
        [list_diff],
    ]


def test_composite_diff_identity_rejects_duplicates(
    fmu_dir: ProjectFMUDirectory, wellbore_mappings: InternalWellboreMappings
) -> None:
    """The diff helper does not silently discard duplicate composite identities."""
    invalid = InternalMappings.model_construct(
        wellbore=InternalWellboreMappings.model_construct(
            root=[wellbore_mappings[0], wellbore_mappings[0]]
        )
    )
    with pytest.raises(ValueError, match="Duplicate composite diff identity"):
        fmu_dir.mappings.get_structured_model_diff(InternalMappings(), invalid)


def test_old_and_new_entries_survive_append_filter_and_merge(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Mixed entries retain their descriptions and structured payloads."""
    old = ChangeInfo(
        change_type=ChangeType.update,
        user="user",
        path=fmu_dir.path,
        change="Updated field 'model.name'. Old value: old -> New value: new",
        hostname="host",
        file="config.json",
        key="model.name",
    )
    old_json = old.model_dump(mode="json", exclude={"structured_diff"})
    fmu_dir.write_text_file(fmu_dir.changelog.relative_path, json.dumps([old_json]))
    assert fmu_dir.changelog.load()[0].structured_diff is None
    new = old.model_copy(
        update={
            "change": "Updated field 'model.name'.",
            "structured_diff": [
                ScalarFieldDiff(field_path="model.name", before="new", after="newer")
            ],
        }
    )
    fmu_dir.changelog.merge_changes([new])
    entries = fmu_dir.changelog.filter_log(
        Filter(
            field_name="file",
            filter_value="config.json",
            filter_type=FilterType.text,
            operator="==",
        )
    )
    assert list(entries) == [old, new]
    assert fmu_dir.changelog.load(force=True)[0].change == old.change
    with pytest.raises(ValueError, match="Invalid filter type"):
        fmu_dir.changelog.filter_log(
            Filter(
                field_name="structured_diff",
                filter_value="[]",
                filter_type=FilterType.text,
                operator="==",
            )
        )


def test_diff_json_roundtrip_preserves_values(fmu_dir: ProjectFMUDirectory) -> None:
    """Pydantic serializes typed values without relying on their Python repr."""

    class NestedValue(BaseModel):
        """A value with types that need JSON serialization."""

        uuid: UUID
        path: Path
        date: datetime
        system: DataSystem

    typed = NestedValue(
        uuid=UUID(int=2),
        path=Path("a/b"),
        date=datetime(2026, 1, 1, tzinfo=UTC),
        system=DataSystem.rms,
    )
    values: list[Any] = [None, False, 0, "", [], typed, [typed]]
    diffs: list[ResourceDiff] = [
        ScalarFieldDiff(field_path=str(i), before=value, after=value)
        for i, value in enumerate(values)
    ]
    diffs.append(
        ListFieldDiff(
            field_path="items",
            added=[],
            removed=[],
            updated=[
                ListUpdatedEntry(
                    key=("rms", "smda", "A"),
                    before={"value": typed},
                    after={"value": typed},
                )
            ],
        )
    )
    entry = ChangeInfo(
        change_type=ChangeType.update,
        user="user",
        path=fmu_dir.path,
        change="Updated fields.",
        hostname="host",
        file="config.json",
        key="value",
        structured_diff=diffs,
    )
    loaded = Log[ChangeInfo].model_validate_json(Log([entry]).model_dump_json())[0]
    assert loaded.model_dump(mode="json") == entry.model_dump(mode="json")
