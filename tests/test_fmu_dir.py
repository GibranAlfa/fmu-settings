"""Tests for the ProjectFMUDirectory class."""

import copy
import inspect
import json
import shutil
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from fmu.datamodels.common.masterdata import Masterdata
from fmu.datamodels.context.mappings import (
    DataSystem,
    RelationType,
    StratigraphyIdentifierMapping,
    StratigraphyMappings,
)
from pytest import MonkeyPatch

from fmu.settings import (
    CacheResource,
    __version__,
    find_nearest_fmu_directory,
    get_fmu_directory,
)
from fmu.settings._fmu_dir import (
    FMUDirectoryBase,
    ProjectFMUDirectory,
    UserFMUDirectory,
)
from fmu.settings._readme_texts import PROJECT_README_CONTENT, USER_README_CONTENT
from fmu.settings._resources.changelog_manager import ChangelogManager
from fmu.settings._resources.lock_manager import DEFAULT_LOCK_TIMEOUT, LockManager
from fmu.settings._resources.mappings_manager import MappingsManager
from fmu.settings.models._enums import ChangeType
from fmu.settings.models.change_info import ChangeInfo
from fmu.settings.models.log import Log
from fmu.settings.models.mappings import Mappings


def test_init_existing_directory(fmu_dir: ProjectFMUDirectory) -> None:
    """Tests initializing an ProjectFMUDirectory on an existing .fmu directory."""
    fmu = ProjectFMUDirectory(fmu_dir.base_path)
    assert fmu.path == fmu_dir.path
    assert fmu.base_path == fmu_dir.base_path


def test_get_fmu_directory(fmu_dir: ProjectFMUDirectory) -> None:
    """Tests initializing an ProjectFMUDirectory via get_fmu_directory."""
    fmu = get_fmu_directory(fmu_dir.base_path)
    assert fmu.path == fmu_dir.path
    assert fmu.base_path == fmu_dir.base_path


def test_find_nearest_fmu_directory(
    monkeypatch: MonkeyPatch, fmu_dir: ProjectFMUDirectory
) -> None:
    """Tests initializing an ProjectFMUDirectory via find_nearest_fmu_directory."""
    subdir = fmu_dir.path / "subdir"
    subdir.mkdir()
    subdir2 = fmu_dir.path / "subdir2"
    subdir2.mkdir()
    subsubdir = subdir / "subsubdir"
    subsubdir.mkdir()

    fmu = find_nearest_fmu_directory(str(subsubdir))
    assert fmu.path == fmu_dir.path
    assert fmu.base_path == fmu_dir.base_path

    monkeypatch.chdir(fmu_dir.base_path)
    fmu = find_nearest_fmu_directory()
    assert fmu.path == fmu_dir.path
    assert fmu.base_path == fmu_dir.base_path

    monkeypatch.chdir(subdir2)
    fmu = find_nearest_fmu_directory()
    assert fmu.path == fmu_dir.path
    assert fmu.base_path == fmu_dir.base_path


def test_init_on_missing_directory(tmp_path: Path) -> None:
    """Tests initializing with a missing directory raises."""
    with pytest.raises(
        FileNotFoundError, match=f"No .fmu directory found at {tmp_path}"
    ):
        ProjectFMUDirectory(tmp_path)


def test_init_when_fmu_is_not_a_directory(tmp_path: Path) -> None:
    """Tests initialized on a .fmu non-directory raises."""
    (tmp_path / ".fmu").touch()
    with pytest.raises(
        FileExistsError, match=f".fmu exists at {tmp_path} but is not a directory"
    ):
        ProjectFMUDirectory(tmp_path)


def test_init_logs_warning_and_uses_default_cache_revisions_on_config_read_error(
    tmp_path: Path,
) -> None:
    """Tests project init falls back to default cache revisions and logs warning."""
    (tmp_path / ".fmu").mkdir()

    with (
        patch(
            "fmu.settings._fmu_dir.ProjectConfigManager.get",
            side_effect=ValueError("bad config"),
        ),
        patch("fmu.settings._fmu_dir.logger.warning") as mock_warning,
    ):
        fmu = ProjectFMUDirectory(tmp_path)

    assert fmu.cache.max_revisions == 5  # noqa: PLR2004
    mock_warning.assert_called_once()
    warning_message = mock_warning.call_args.args[0]
    assert "project config" in warning_message
    assert "bad config" in warning_message


def test_find_fmu_directory(fmu_dir: ProjectFMUDirectory) -> None:
    """Tests find_fmu_directory method on nested children."""
    child = fmu_dir.base_path / "child"
    grand_child = child / "grandchild"
    grand_child.mkdir(parents=True)

    found_dir = ProjectFMUDirectory.find_fmu_directory(grand_child)
    assert found_dir == fmu_dir.path


def test_find_fmu_directory_not_found(tmp_path: Path) -> None:
    """Tests find_fmu_directory() returns None if no .fmu found."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    found_dir = ProjectFMUDirectory.find_fmu_directory(empty_dir)
    assert found_dir is None


def test_find_nearest(fmu_dir: ProjectFMUDirectory) -> None:
    """Test find_nearest factory method."""
    subdir = fmu_dir.base_path / "subdir"
    subdir.mkdir()

    fmu = ProjectFMUDirectory.find_nearest(subdir)
    assert fmu.path == fmu_dir.path


def test_find_nearest_not_found(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """Test find_nearest raises FileNotFoundError when not found."""
    monkeypatch.chdir(tmp_path)
    with pytest.raises(
        FileNotFoundError, match=f"No .fmu directory found at or above {tmp_path}"
    ):
        ProjectFMUDirectory.find_nearest()
    with pytest.raises(
        FileNotFoundError, match=f"No .fmu directory found at or above {tmp_path}"
    ):
        ProjectFMUDirectory.find_nearest(tmp_path)


def test_cache_property_returns_cached_manager(fmu_dir: ProjectFMUDirectory) -> None:
    """Cache manager should be memoized and ready for use."""
    cache = fmu_dir.cache

    assert cache is fmu_dir.cache
    assert fmu_dir._cache_manager is cache
    assert cache.max_revisions == 5  # noqa: PLR2004


def test_set_cache_max_revisions_updates_manager(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Changing retention should update the existing cache manager."""
    cache = fmu_dir.cache
    fmu_dir.cache_max_revisions = 7

    assert cache.max_revisions == 7  # noqa: PLR2004


def test_set_cache_max_revisions_does_not_create_config_snapshot(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Changing retention should not add a new config.json cache revision."""
    initial_revisions = fmu_dir.cache.list_revisions("config.json")

    fmu_dir.cache_max_revisions = 10

    assert fmu_dir.cache.list_revisions("config.json") == initial_revisions


def test_set_cache_max_revisions_decrease_trims_existing_revisions(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Decreasing retention prunes excess cached revisions immediately."""
    initial_snapshot_count = 10
    expected_snapshot_count = 5
    fmu_dir.cache_max_revisions = initial_snapshot_count
    for i in range(initial_snapshot_count):
        fmu_dir.cache.store_revision("foo.json", f"content_{i}", skip_trim=True)

    fmu_dir.cache_max_revisions = expected_snapshot_count

    snapshots = sorted((fmu_dir.path / "cache" / "foo").iterdir())
    assert len(snapshots) == expected_snapshot_count
    assert [snapshot.read_text(encoding="utf-8") for snapshot in snapshots] == [
        "content_5",
        "content_6",
        "content_7",
        "content_8",
        "content_9",
    ]


def test_set_cache_max_revisions_decrease_is_noop_within_limit(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Decreasing retention does not delete revisions already within limit."""
    fmu_dir.cache_max_revisions = 10
    for i in range(5):
        fmu_dir.cache.store_revision("foo.json", f"content_{i}", skip_trim=True)

    fmu_dir.cache_max_revisions = 5

    snapshots = sorted((fmu_dir.path / "cache" / "foo").iterdir())
    assert len(snapshots) == 5  # noqa: PLR2004
    assert [snapshot.read_text(encoding="utf-8") for snapshot in snapshots] == [
        "content_0",
        "content_1",
        "content_2",
        "content_3",
        "content_4",
    ]


def test_changelog_property_returns_changelog_manager(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Changelog manager should be memoized and ready for use."""
    assert isinstance(fmu_dir.changelog, ChangelogManager)
    assert fmu_dir.changelog is fmu_dir._changelog


def test_mappings_property_returns_mappings_manager(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Mappings manager should be memoized and ready for use."""
    assert isinstance(fmu_dir.mappings, MappingsManager)
    assert fmu_dir.mappings is fmu_dir._mappings


def test_get_cache_content_returns_model(fmu_dir: ProjectFMUDirectory) -> None:
    """Cache content should be returned as a validated model."""
    cached_config = fmu_dir.config.load().model_copy(update={"version": "1.2.3"})
    snapshot = fmu_dir.cache.store_revision(
        CacheResource.config.value,
        cached_config.model_dump_json(by_alias=True, indent=2),
    )
    assert snapshot is not None

    cache_content = fmu_dir.get_cache_content(
        CacheResource.config.value,
        snapshot.name,
    )

    assert cache_content.model_dump() == cached_config.model_dump()


def test_get_cache_content_raises_for_unsupported_resource(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Unsupported cache resources should raise."""
    with pytest.raises(ValueError, match="not supported for cache operations"):
        fmu_dir.get_cache_content("unsupported.json", "missing.json")


def test_restore_from_cache_restores_mappings(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Restoring mappings should refresh the resource cache."""
    cached_mapping = StratigraphyIdentifierMapping(
        source_system=DataSystem.rms,
        target_system=DataSystem.smda,
        relation_type=RelationType.primary,
        source_id="TopVolantis",
        target_id="VOLANTIS GP. Top",
    )
    cached_mappings = Mappings(stratigraphy=StratigraphyMappings(root=[cached_mapping]))
    snapshot = fmu_dir.cache.store_revision(
        CacheResource.mappings.value,
        cached_mappings.model_dump_json(by_alias=True, indent=2),
    )
    assert snapshot is not None

    current_mapping = StratigraphyIdentifierMapping(
        source_system=DataSystem.rms,
        target_system=DataSystem.smda,
        relation_type=RelationType.primary,
        source_id="TopTherys",
        target_id="THERYS GP. Top",
    )
    current_mappings = Mappings(
        stratigraphy=StratigraphyMappings(root=[current_mapping])
    )
    fmu_dir.mappings.save(current_mappings)

    fmu_dir.restore_from_cache(CacheResource.mappings.value, snapshot.name)

    assert fmu_dir.mappings._cache is not None
    assert fmu_dir.mappings._cache.model_dump() == cached_mappings.model_dump()
    restored = fmu_dir.mappings.load()
    assert restored.model_dump() == cached_mappings.model_dump()


def test_restore_from_cache_raises_for_unsupported_resource(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Unsupported cache resources should raise on restore."""
    with pytest.raises(ValueError, match="not supported for cache restoration"):
        fmu_dir.restore_from_cache("unsupported.json", "missing.json")


def test_get_config_value(fmu_dir: ProjectFMUDirectory) -> None:
    """Tests get_config_value retrieves correctly from the config."""
    assert fmu_dir.get_config_value("version") == __version__
    assert fmu_dir.get_config_value("created_by") == "user"


def test_set_config_value(fmu_dir: ProjectFMUDirectory) -> None:
    """Tests set_config_value sets and writes the result."""
    fmu_dir.set_config_value("version", "200.0.0")
    with open(fmu_dir.config.path, encoding="utf-8") as f:
        config_dict = json.loads(f.read())

    assert config_dict["version"] == "200.0.0"
    assert fmu_dir.get_config_value("version") == "200.0.0"
    assert fmu_dir.config.load().version == "200.0.0"


def test_update_config(fmu_dir: ProjectFMUDirectory) -> None:
    """Tests update_config updates and saves the config for multiple values."""
    updated_config = fmu_dir.update_config({"version": "2.0.0", "created_by": "user2"})

    assert updated_config.version == "2.0.0"
    assert updated_config.created_by == "user2"

    assert fmu_dir.config.load() is not None
    assert fmu_dir.get_config_value("version", None) == "2.0.0"
    assert fmu_dir.get_config_value("created_by", None) == "user2"

    config_file = fmu_dir.config.path
    with open(config_file, encoding="utf-8") as f:
        saved_config = json.load(f)

    assert saved_config["version"] == "2.0.0"
    assert saved_config["created_by"] == "user2"


def test_update_config_invalid_data(fmu_dir: ProjectFMUDirectory) -> None:
    """Tests that update_config raises ValidationError on bad data."""
    updates = {"version": 123}
    with pytest.raises(
        ValueError,
        match=f"Invalid value set for 'ProjectConfigManager' with updates '{updates}'",
    ):
        fmu_dir.update_config(updates)


def test_get_file_path(fmu_dir: ProjectFMUDirectory) -> None:
    """Tests get_file_path returns correct path."""
    path = fmu_dir.get_file_path("test.txt")
    assert path == fmu_dir.path / "test.txt"


def test_file_exists(fmu_dir: ProjectFMUDirectory) -> None:
    """Tests file_exists returns correct boolean."""
    test_file = fmu_dir.path / "exists.txt"
    test_file.touch()

    assert fmu_dir.file_exists("exists.txt") is True
    assert fmu_dir.file_exists("doesnt.txt") is False


def test_read_file(fmu_dir: ProjectFMUDirectory) -> None:
    """Tests read_file reads bytes correctly."""
    test_file = fmu_dir.path / "bin.dat"
    test_data = b"test bin data"
    test_file.write_bytes(test_data)

    data = fmu_dir.read_file("bin.dat")
    assert data == test_data


def test_read_file_not_found(fmu_dir: ProjectFMUDirectory) -> None:
    """Tests read_file raises FileNotFoundError for missing files."""
    with pytest.raises(FileNotFoundError, match="No such file or directory"):
        fmu_dir.read_file("not_real.txt")


def test_read_text_file(fmu_dir: ProjectFMUDirectory) -> None:
    """Tests read_text_file reads text correctly."""
    test_file = fmu_dir.path / "text.txt"
    test_text = "test text data å"
    test_file.write_text(test_text)

    text = fmu_dir.read_text_file("text.txt")
    assert text == test_text


def test_write_text_file(fmu_dir: ProjectFMUDirectory) -> None:
    """Tests write_text_file writes text correctly."""
    test_text = "new text data æ"
    fmu_dir.write_text_file("new_text.txt", test_text)

    file_path = fmu_dir.path / "new_text.txt"
    assert file_path.exists()
    assert file_path.read_text() == test_text


def test_write_file_creates_dir(fmu_dir: ProjectFMUDirectory) -> None:
    """Tests write_file creates parent directories."""
    test_data = b"nested data"
    fmu_dir.write_file("nested/dir/file.dat", test_data)

    nested_dir = fmu_dir.path / "nested" / "dir"
    assert nested_dir.is_dir()

    file_path = nested_dir / "file.dat"
    assert file_path.exists()
    assert file_path.read_bytes() == test_data


def test_write_operations_raise_when_locked(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Tests write helpers raise when another process holds the lock."""
    lock = LockManager(fmu_dir)
    with (
        patch("socket.gethostname", return_value="other-host"),
        patch("os.getpid", return_value=12345),
    ):
        lock.acquire()

    with pytest.raises(PermissionError, match="Cannot write to .fmu directory"):
        fmu_dir.write_text_file("blocked.txt", "blocked")

    with pytest.raises(PermissionError, match="Cannot write to .fmu directory"):
        fmu_dir.write_file("blocked.bin", b"blocked")

    with (
        patch("socket.gethostname", return_value="other-host"),
        patch("os.getpid", return_value=12345),
    ):
        lock.release()


def test_list_files(fmu_dir: ProjectFMUDirectory) -> None:
    """Tests that list_files returns the correct files."""
    (fmu_dir.path / "file1.txt").touch()
    (fmu_dir.path / "file2.txt").touch()

    subdir = fmu_dir.path / "subdir"
    subdir.mkdir()
    (subdir / "file3.txt").touch()

    files = fmu_dir.list_files()
    filenames = [f.name for f in files]

    assert "file1.txt" in filenames
    assert "file2.txt" in filenames
    assert "config.json" in filenames

    assert "file3.txt" not in filenames

    subdir_files = fmu_dir.list_files("subdir")
    assert len(subdir_files) == 1
    assert subdir_files[0].name == "file3.txt"

    not_subdir_files = fmu_dir.list_files("not_subdir")
    assert not_subdir_files == []


def test_ensure_directory(fmu_dir: ProjectFMUDirectory) -> None:
    """Tests that ensure_directory creates directories."""
    dir_path = fmu_dir.ensure_directory("nested/test/dir")
    assert dir_path.exists()
    assert dir_path.is_dir()


def test_user_init_existing_directory(user_fmu_dir: UserFMUDirectory) -> None:
    """Tests initializing an ProjectFMUDirectory on an existing .fmu directory."""
    with patch("pathlib.Path.home", return_value=user_fmu_dir.base_path):
        fmu = UserFMUDirectory()

    assert fmu.path == user_fmu_dir.path
    assert fmu.base_path == user_fmu_dir.base_path


def test_user_init_on_missing_directory(tmp_path: Path) -> None:
    """Tests initializing with a missing directory raises."""
    with (
        patch("pathlib.Path.home", return_value=tmp_path),
        pytest.raises(
            FileNotFoundError, match=f"No .fmu directory found at {tmp_path}"
        ),
    ):
        UserFMUDirectory()


def test_user_init_when_fmu_is_not_a_directory(tmp_path: Path) -> None:
    """Tests initialized on a .fmu non-directory raises."""
    (tmp_path / ".fmu").touch()
    with (
        patch("pathlib.Path.home", return_value=tmp_path),
        pytest.raises(
            FileExistsError, match=f".fmu exists at {tmp_path} but is not a directory"
        ),
    ):
        UserFMUDirectory()


def test_user_init_logs_warning_and_uses_default_cache_revisions_on_config_read_error(
    tmp_path: Path,
) -> None:
    """Tests user init falls back to default cache revisions and logs warning."""
    (tmp_path / ".fmu").mkdir()

    with (
        patch("pathlib.Path.home", return_value=tmp_path),
        patch(
            "fmu.settings._fmu_dir.UserConfigManager.get",
            side_effect=FileNotFoundError("missing"),
        ),
        patch("fmu.settings._fmu_dir.logger.warning") as mock_warning,
    ):
        fmu = UserFMUDirectory()

    assert fmu.cache.max_revisions == 5  # noqa: PLR2004
    mock_warning.assert_called_once()
    warning_message = mock_warning.call_args.args[0]
    assert "user config" in warning_message
    assert "missing" in warning_message


def test_update_user_config(user_fmu_dir: UserFMUDirectory) -> None:
    """Tests update_config updates and saves the user config for multiple values."""
    recent_dir = "/foo/bar"
    updated_config = user_fmu_dir.update_config(
        {"version": "2.0.0", "recent_project_directories": [recent_dir]}
    )

    assert updated_config.version == "2.0.0"
    assert updated_config.recent_project_directories == [Path(recent_dir)]

    assert user_fmu_dir.config.load() is not None
    assert user_fmu_dir.get_config_value("version", None) == "2.0.0"
    assert user_fmu_dir.get_config_value("recent_project_directories") == [
        Path(recent_dir)
    ]

    config_file = user_fmu_dir.config.path
    with open(config_file, encoding="utf-8") as f:
        saved_config = json.load(f)

    assert saved_config["version"] == "2.0.0"
    assert saved_config["recent_project_directories"] == [recent_dir]


def test_update_user_config_invalid_data(user_fmu_dir: UserFMUDirectory) -> None:
    """Tests that update_config raises ValidationError on bad data."""
    updates = {"recent_project_directories": [123]}
    with pytest.raises(
        ValueError,
        match="Invalid value set for 'UserConfigManager' with updates "
        "'{'recent_project_directories':",
    ):
        user_fmu_dir.update_config(updates)


def test_update_user_config_non_unique_recent_projects(
    user_fmu_dir: UserFMUDirectory,
) -> None:
    """Tests that update_config raises on non-unique recent_project_directories."""
    updates = {"recent_project_directories": [Path("/foo/bar"), Path("/foo/bar")]}
    with pytest.raises(ValueError, match="unique entries"):
        user_fmu_dir.update_config(updates)


def test_acquire_lock_on_project_fmu(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Tests that a lock can be acquired on the project dir."""
    fmu_dir._lock.acquire()
    assert fmu_dir._lock.is_acquired()
    assert fmu_dir._lock.exists
    assert (fmu_dir.path / ".lock").exists()


def test_acquire_lock_on_user_fmu(
    user_fmu_dir: UserFMUDirectory,
) -> None:
    """Tests that a lock can be acquired on the user dir."""
    user_fmu_dir._lock.acquire()
    assert user_fmu_dir._lock.is_acquired()
    assert user_fmu_dir._lock.exists
    assert (user_fmu_dir.path / ".lock").exists()


def test_restore_rebuilds_project_fmu_from_cache(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Tests that restore should recreate missing files using cached config data."""
    fmu_dir.update_config({"version": "123.4.5"})
    cached_dump = json.loads((fmu_dir.path / "config.json").read_text())
    cached_mapping = StratigraphyIdentifierMapping(
        source_system=DataSystem.rms,
        target_system=DataSystem.smda,
        relation_type=RelationType.primary,
        source_id="TopVolantis",
        target_id="VOLANTIS GP. Top",
    )
    fmu_dir.mappings.update_stratigraphy_mappings(
        StratigraphyMappings(root=[cached_mapping])
    )
    cached_mappings_dump = json.loads((fmu_dir.path / "mappings.json").read_text())

    shutil.rmtree(fmu_dir.path)
    assert not fmu_dir.path.exists()

    restored_files = fmu_dir.restore()

    assert fmu_dir.path.exists()
    assert restored_files == [
        Path("README"),
        Path("config.json"),
        Path("mappings.json"),
    ]
    readme_path = fmu_dir.path / "README"
    assert readme_path.exists()
    assert readme_path.read_text() == PROJECT_README_CONTENT

    restored_dump = json.loads((fmu_dir.path / "config.json").read_text())

    cached_dump.pop("last_modified_at", None)
    restored_dump.pop("last_modified_at", None)
    assert restored_dump == cached_dump
    assert (fmu_dir.path / "mappings.json").exists()
    restored_mappings_dump = json.loads((fmu_dir.path / "mappings.json").read_text())
    assert restored_mappings_dump == cached_mappings_dump

    cache_dir = fmu_dir.path / "cache" / "config"
    assert cache_dir.is_dir()
    assert any(cache_dir.iterdir())
    mappings_cache_dir = fmu_dir.path / "cache" / "mappings"
    assert mappings_cache_dir.is_dir()
    assert any(mappings_cache_dir.iterdir())


def test_restore_resets_when_cache_missing(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Tests that restore should fall back to reset when no cached config exists."""
    fmu_dir.config._cache = None
    shutil.rmtree(fmu_dir.path)
    assert not fmu_dir.path.exists()

    with patch.object(
        fmu_dir.config, "reset", wraps=fmu_dir.config.reset
    ) as mock_reset:
        restored_files = fmu_dir.restore()

    mock_reset.assert_called_once()
    assert restored_files == [Path("README"), Path("config.json")]
    assert fmu_dir.path.exists()
    readme_path = fmu_dir.path / "README"
    assert readme_path.exists()
    assert readme_path.read_text() == PROJECT_README_CONTENT
    assert (fmu_dir.config.path).exists()


def test_restore_rebuilds_user_fmu(user_fmu_dir: UserFMUDirectory) -> None:
    """Tests that user FMU restore should recreate missing files using cached state."""
    cached_dump = json.loads((user_fmu_dir.path / "config.json").read_text())

    shutil.rmtree(user_fmu_dir.path)
    assert not user_fmu_dir.path.exists()

    restored_files = user_fmu_dir.restore()

    assert user_fmu_dir.path.exists()
    assert restored_files == [Path("README"), Path("config.json")]
    readme_path = user_fmu_dir.path / "README"
    assert readme_path.exists()
    assert readme_path.read_text() == USER_README_CONTENT

    restored_dump = json.loads((user_fmu_dir.path / "config.json").read_text())

    cached_dump.pop("last_modified_at", None)
    restored_dump.pop("last_modified_at", None)
    assert restored_dump == cached_dump


def test_list_restorable_files_reports_missing_project_files(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Tests list_restorable_files reports only files restore would recreate."""
    cached_mapping = StratigraphyIdentifierMapping(
        source_system=DataSystem.rms,
        target_system=DataSystem.smda,
        relation_type=RelationType.primary,
        source_id="TopVolantis",
        target_id="VOLANTIS GP. Top",
    )
    fmu_dir.mappings.update_stratigraphy_mappings(
        StratigraphyMappings(root=[cached_mapping])
    )

    (fmu_dir.path / "README").unlink()
    fmu_dir.config.path.unlink()
    fmu_dir.mappings.path.unlink()

    assert fmu_dir.list_restorable_files() == [
        Path("README"),
        Path("config.json"),
        Path("mappings.json"),
    ]


def test_list_restorable_files_skips_project_mappings_without_cache(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Tests list_restorable_files excludes mappings without cached content."""
    fmu_dir.mappings._cache = None
    if fmu_dir.mappings.path.exists():
        fmu_dir.mappings.path.unlink()

    assert fmu_dir.list_restorable_files() == []


def test_fmu_directory_base_exposes_lock_timeout_kwarg() -> None:
    """Tests that the kw-only lock timeout argument remains available."""
    signature = inspect.signature(FMUDirectoryBase.__init__)
    lock_timeout = signature.parameters.get("lock_timeout_seconds")

    assert lock_timeout is not None, "lock_timeout_seconds kwarg missing from base init"
    assert lock_timeout.kind is inspect.Parameter.KEYWORD_ONLY
    assert lock_timeout.default == DEFAULT_LOCK_TIMEOUT


def test_find_rms_projects_none_found(fmu_dir: ProjectFMUDirectory) -> None:
    """Test finding RMS projects when none exist."""
    projects = fmu_dir.find_rms_projects()
    assert projects == []


def test_find_rms_projects_single(fmu_dir: ProjectFMUDirectory) -> None:
    """Test finding a single RMS project."""
    rms_project = fmu_dir.base_path / "rms" / "model" / "test.rms"
    rms_project.mkdir(parents=True)
    (rms_project / ".master").write_text("master content")
    (rms_project / "rms.ini").write_text("[RMS]")

    projects = fmu_dir.find_rms_projects()

    assert len(projects) == 1
    assert projects[0] == rms_project


def test_find_rms_projects_multiple(fmu_dir: ProjectFMUDirectory) -> None:
    """Test finding multiple RMS projects."""
    rms_project_1 = fmu_dir.base_path / "rms" / "model" / "drogon.rms14.2.2"
    rms_project_1.mkdir(parents=True)
    (rms_project_1 / ".master").write_text("master content")
    (rms_project_1 / "rms.ini").write_text("[RMS]")

    rms_project_2 = fmu_dir.base_path / "rms" / "model" / "drogon.rms14.1.0"
    rms_project_2.mkdir(parents=True)
    (rms_project_2 / ".master").write_text("master content")
    (rms_project_2 / "rms.ini").write_text("[RMS]")

    projects = fmu_dir.find_rms_projects()

    assert len(projects) == 2  # noqa: PLR2004
    assert set(projects) == {rms_project_1, rms_project_2}


def test_find_rms_projects_incomplete_missing_master(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Test that projects missing .master file are not included."""
    incomplete = fmu_dir.base_path / "rms" / "model" / "incomplete"
    incomplete.mkdir(parents=True)
    (incomplete / "rms.ini").write_text("[RMS]")

    projects = fmu_dir.find_rms_projects()
    assert projects == []


def test_find_rms_projects_incomplete_missing_ini(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Test that projects missing rms.ini file are not included."""
    incomplete = fmu_dir.base_path / "rms" / "model" / "incomplete"
    incomplete.mkdir(parents=True)
    (incomplete / ".master").write_text("master content")

    projects = fmu_dir.find_rms_projects()
    assert projects == []


def test_find_rms_projects_ignores_files_in_model_dir(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Test that extra files in rms/model do not affect detection."""
    model_dir = fmu_dir.base_path / "rms" / "model"
    model_dir.mkdir(parents=True)
    (model_dir / "not_a_directory.txt").write_text("some file")
    rms_project = model_dir / "valid.rms"
    rms_project.mkdir()
    (rms_project / ".master").write_text("content")
    (rms_project / "rms.ini").write_text("[RMS]")

    projects = fmu_dir.find_rms_projects()

    assert len(projects) == 1
    assert projects[0] == rms_project


def test_find_rms_projects_ignores_rms_model_as_file(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Test that rms/model path that is a file is ignored."""
    rms_dir = fmu_dir.base_path / "rms"
    rms_dir.mkdir()
    (rms_dir / "model").write_text("not a directory")

    project = fmu_dir.find_rms_projects()

    assert len(project) == 0


def test_find_rms_projects_ignores_model_directory_in_subfolders_of_project_root(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Test that rms/model under subfolders of the root is ignored."""
    invalid_model_location = fmu_dir.base_path / "subfolder" / "rms" / "model"
    invalid_model_location.mkdir(parents=True)
    (invalid_model_location / ".master").write_text("content")
    (invalid_model_location / "rms.ini").write_text("[RMS]")

    projects = fmu_dir.find_rms_projects()

    assert len(projects) == 0


def test_find_rms_projects_with_config_path(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Test storing and retrieving RMS project path in config."""
    rms_project = fmu_dir.base_path / "rms" / "model" / "my.rms"
    rms_project.mkdir(parents=True)
    (rms_project / ".master").write_text("content")
    (rms_project / "rms.ini").write_text("[RMS]")

    fmu_dir.set_config_value("rms", {"path": str(rms_project), "version": "14.2.2"})

    stored_rms = fmu_dir.get_config_value("rms")
    assert stored_rms.path == rms_project

    fmu_dir2 = ProjectFMUDirectory(fmu_dir.base_path)
    assert fmu_dir2.get_config_value("rms").path == rms_project


def test_fmu_directory_base_get_dir_diff_with_other_fmu_dir(
    fmu_dir: ProjectFMUDirectory,
    extra_fmu_dir: ProjectFMUDirectory,
    masterdata_dict: dict[str, Any],
) -> None:
    """Tests getting the resource diff with another .fmu directory."""
    new_fmu_dir = extra_fmu_dir
    new_fmu_dir.set_config_value("masterdata", masterdata_dict)
    diff_fmu_dir = fmu_dir.get_dir_diff(new_fmu_dir)

    assert len(diff_fmu_dir) == 1
    assert "config" in diff_fmu_dir
    assert len(diff_fmu_dir["config"]) == 1
    assert diff_fmu_dir["config"][0][0] == "masterdata"
    assert diff_fmu_dir["config"][0][1] is None
    assert diff_fmu_dir["config"][0][2] == Masterdata.model_validate(masterdata_dict)


def test_fmu_directory_base_get_dir_diff_only_diff_whitelisted_resources(
    fmu_dir: ProjectFMUDirectory,
    extra_fmu_dir: ProjectFMUDirectory,
    masterdata_dict: dict[str, Any],
) -> None:
    """Tests that only the whitelisted resources are diffed."""
    new_fmu_dir = extra_fmu_dir
    new_fmu_dir.set_config_value("masterdata", masterdata_dict)
    new_fmu_dir._lock.acquire()

    assert new_fmu_dir._changelog.exists
    assert new_fmu_dir._lock.exists
    assert not fmu_dir._changelog.exists
    assert not fmu_dir._lock.exists

    diff_fmu_dir = fmu_dir.get_dir_diff(new_fmu_dir)

    assert len(diff_fmu_dir) == 1
    assert diff_fmu_dir["config"]
    assert "_lock" not in diff_fmu_dir


def test_fmu_directory_base_get_dir_diff_skip_when_resource_not_exist(
    fmu_dir: ProjectFMUDirectory,
    extra_fmu_dir: ProjectFMUDirectory,
) -> None:
    """Tests that sync is skipped for resources that does not exist.

    When a resource does not exist in one of the .fmu directories,
    sync is skipped for that resource.
    """
    new_fmu_dir = extra_fmu_dir
    new_fmu_dir.config.path.unlink()

    diff_fmu_dir = fmu_dir.get_dir_diff(new_fmu_dir)
    assert len(diff_fmu_dir) == 0


def test_fmu_directory_base_sync_dir_with_other_fmu_dir(
    fmu_dir: ProjectFMUDirectory,
    extra_fmu_dir: ProjectFMUDirectory,
    masterdata_dict: dict[str, Any],
) -> None:
    """Tests syncing resources with another .fmu directory."""
    new_fmu_dir = extra_fmu_dir
    new_fmu_dir.set_config_value("masterdata", masterdata_dict)

    assert new_fmu_dir.config.load().masterdata
    assert not fmu_dir.config.load().masterdata

    updated_resources = fmu_dir.sync_dir(new_fmu_dir)

    assert len(updated_resources) == 1
    assert "config" in updated_resources
    assert updated_resources["config"].masterdata == Masterdata.model_validate(
        masterdata_dict
    )
    assert new_fmu_dir.config.load().masterdata == fmu_dir.config.load().masterdata


def test_fmu_directory_base_sync_dir_only_whitelisted_resources(
    fmu_dir: ProjectFMUDirectory,
    extra_fmu_dir: ProjectFMUDirectory,
    masterdata_dict: dict[str, Any],
) -> None:
    """Tests that only the whitelisted resources are synced."""
    new_fmu_dir = extra_fmu_dir
    new_fmu_dir.set_config_value("masterdata", masterdata_dict)
    new_fmu_dir._lock.acquire()

    assert new_fmu_dir._changelog.exists
    assert new_fmu_dir._lock.exists
    assert not fmu_dir._changelog.exists
    assert not fmu_dir._lock.exists

    updates = fmu_dir.sync_dir(new_fmu_dir)

    assert "_lock" not in updates
    assert len(updates) == 1
    assert updates["config"]
    assert not fmu_dir._lock.exists


def test_fmu_directory_base_sync_dir_skip_when_resource_not_exist(
    fmu_dir: ProjectFMUDirectory,
    extra_fmu_dir: ProjectFMUDirectory,
) -> None:
    """Tests that sync is skipped for resources that does not exist.

    When a resource does not exist in one of the .fmu directories,
    sync is skipped for that resource.
    """
    new_fmu_dir = extra_fmu_dir
    new_fmu_dir.config.path.unlink()
    updates = fmu_dir.sync_dir(new_fmu_dir)
    assert len(updates) == 0


def test_fmu_directory_base_sync_dir_skip_when_no_diff(
    fmu_dir: ProjectFMUDirectory,
    extra_fmu_dir: ProjectFMUDirectory,
) -> None:
    """Tests that sync is skipped for resources with no diff.

    When doing a sync of two equal resources, sync is skipped for that resource.
    """
    new_fmu_dir = extra_fmu_dir
    assert fmu_dir.config.exists
    assert new_fmu_dir.config.exists
    assert fmu_dir.config.load() == new_fmu_dir.config.load()

    updates = fmu_dir.sync_dir(new_fmu_dir)
    assert len(updates) == 0


def test_fmu_directory_base_sync_runtime_variables(
    fmu_dir: ProjectFMUDirectory,
    extra_fmu_dir: ProjectFMUDirectory,
) -> None:
    """Tests that runtime variables are synced as part of .fmu directory sync.

    When resources in the .fmu directory are synced,
    runtime variables should be synced accordingly.
    """
    new_fmu_dir = extra_fmu_dir
    new_cache_max_revisions = 10
    old_cache_max_revisions = fmu_dir.config.load().cache_max_revisions
    assert fmu_dir.cache_max_revisions != new_cache_max_revisions
    assert fmu_dir.cache_max_revisions == fmu_dir.config.load().cache_max_revisions

    new_config = new_fmu_dir.config.load()
    new_config.cache_max_revisions = new_cache_max_revisions
    new_fmu_dir.config.save(new_config)

    updates = fmu_dir.sync_dir(new_fmu_dir)
    assert "config" in updates
    assert updates["config"].cache_max_revisions == new_cache_max_revisions
    assert fmu_dir.cache_max_revisions == new_cache_max_revisions
    assert fmu_dir.cache.max_revisions == new_cache_max_revisions

    config = fmu_dir.config.load()
    assert config.cache_max_revisions is new_cache_max_revisions
    config.cache_max_revisions = old_cache_max_revisions
    fmu_dir.config.save(config)
    assert (
        fmu_dir.config.load(force=True).cache_max_revisions == old_cache_max_revisions
    )
    assert fmu_dir.cache_max_revisions == new_cache_max_revisions
    assert fmu_dir.cache.max_revisions == new_cache_max_revisions

    fmu_dir._sync_runtime_variables()

    assert fmu_dir.cache_max_revisions == old_cache_max_revisions
    assert fmu_dir.cache.max_revisions == old_cache_max_revisions


def test_restore_from_cache_syncs_runtime_variables(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Tests config restore updates runtime cache retention variables."""
    current_config = fmu_dir.config.load()
    original_cache_max_revisions = current_config.cache_max_revisions
    restored_cache_max_revisions = original_cache_max_revisions + 1

    updated_config = current_config.model_copy(
        update={"cache_max_revisions": restored_cache_max_revisions}
    )
    revision_path = fmu_dir.cache.store_revision(
        Path("config.json"),
        updated_config.model_dump_json(by_alias=True, indent=2),
    )
    assert revision_path is not None

    fmu_dir.restore_from_cache("config.json", revision_path.name)

    assert fmu_dir.config.load(force=True).cache_max_revisions == (
        restored_cache_max_revisions
    )
    assert fmu_dir.cache_max_revisions == restored_cache_max_revisions
    assert fmu_dir.cache.max_revisions == restored_cache_max_revisions


def test_restore_from_cache_restores_runtime_retention_on_config_restore_failure(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Failed config restores should restore the previous runtime retention."""
    current_config = fmu_dir.config.load()
    original_cache_max_revisions = current_config.cache_max_revisions
    restored_cache_max_revisions = original_cache_max_revisions + 1

    restored_config = current_config.model_copy(
        update={"cache_max_revisions": restored_cache_max_revisions}
    )
    revision_path = fmu_dir.cache.store_revision(
        Path("config.json"),
        restored_config.model_dump_json(by_alias=True, indent=2),
    )
    assert revision_path is not None

    with (
        patch.object(
            fmu_dir.cache,
            "restore_revision",
            side_effect=RuntimeError("restore failed"),
        ),
        pytest.raises(RuntimeError, match="restore failed"),
    ):
        fmu_dir.restore_from_cache("config.json", revision_path.name)

    assert fmu_dir.config.load(force=True).cache_max_revisions == (
        original_cache_max_revisions
    )
    assert fmu_dir.cache_max_revisions == original_cache_max_revisions
    assert fmu_dir.cache.max_revisions == original_cache_max_revisions


def test_restore_from_cache_lower_cache_max_revisions_trims_all_resources(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Restoring config.json with a lower limit trims existing cached resources."""
    initial_max_revisions = 10
    restored_max_revisions = 5

    fmu_dir.cache_max_revisions = initial_max_revisions
    for i in range(initial_max_revisions):
        fmu_dir.cache.store_revision("foo.json", f"content_{i}", skip_trim=True)

    current_config = fmu_dir.config.load()
    restored_config = current_config.model_copy(
        update={"cache_max_revisions": restored_max_revisions}
    )
    revision_path = fmu_dir.cache.store_revision(
        Path("config.json"),
        restored_config.model_dump_json(by_alias=True, indent=2),
        skip_trim=True,
    )
    assert revision_path is not None

    fmu_dir.restore_from_cache("config.json", revision_path.name)

    assert fmu_dir.cache_max_revisions == restored_max_revisions
    assert fmu_dir.cache.max_revisions == restored_max_revisions
    assert len(fmu_dir.cache.list_revisions("foo.json")) == restored_max_revisions


def test_restore_from_cache_higher_cache_max_revisions_does_not_trim_to_old_limit(
    fmu_dir: ProjectFMUDirectory,
) -> None:
    """Restoring config.json with a higher limit keeps the pre-restore snapshot."""
    current_config = fmu_dir.config.load()
    current_max_revisions = 5
    restored_max_revisions = 10
    extra_config_revisions = 6

    assert current_config.cache_max_revisions == current_max_revisions

    for _ in range(extra_config_revisions):
        fmu_dir.cache.store_revision(
            Path("config.json"),
            current_config.model_dump_json(by_alias=True, indent=2),
            skip_trim=True,
        )

    restored_config = current_config.model_copy(
        update={"cache_max_revisions": restored_max_revisions}
    )
    revision_path = fmu_dir.cache.store_revision(
        Path("config.json"),
        restored_config.model_dump_json(by_alias=True, indent=2),
        skip_trim=True,
    )
    assert revision_path is not None
    revision_count_before_restore = len(fmu_dir.cache.list_revisions("config.json"))

    fmu_dir.restore_from_cache("config.json", revision_path.name)

    expected_revision_count = revision_count_before_restore + 1

    assert fmu_dir.cache_max_revisions == restored_max_revisions
    assert fmu_dir.cache.max_revisions == restored_max_revisions
    assert len(fmu_dir.cache.list_revisions("config.json")) == expected_revision_count


def test_fmu_directory_base_get_dir_diff_with_same_changelog(
    fmu_dir: ProjectFMUDirectory,
    extra_fmu_dir: ProjectFMUDirectory,
) -> None:
    """Tests getting the changelog diff with equivalent directories."""
    log_entry = ChangeInfo(
        change_type=ChangeType.add,
        user="fmu_dir_user",
        path=Path("/some_path"),
        change="some change",
        hostname="host",
        file="config",
        key="test_key",
    )
    fmu_dir._changelog.add_log_entry(log_entry)
    extra_fmu_dir._changelog.add_log_entry(log_entry)
    dir_diff = fmu_dir.get_dir_diff(extra_fmu_dir)

    for resource, change_list in dir_diff.items():
        assert len(change_list) == 0, f"Resource {resource} has changes"


def test_fmu_directory_base_get_dir_diff_with_changelog(
    fmu_dir: ProjectFMUDirectory,
    extra_fmu_dir: ProjectFMUDirectory,
) -> None:
    """Tests getting the changelog diff with another .fmu directory."""
    log_entry = ChangeInfo(
        change_type=ChangeType.add,
        user="fmu_dir_user",
        path=Path("/some_path"),
        change="some change",
        hostname="host",
        file="config",
        key="test_key",
    )
    fmu_dir._changelog.add_log_entry(log_entry)
    assert len(fmu_dir._changelog.load()) == 1
    assert fmu_dir._changelog.load()[0] == log_entry

    new_fmu_dir = extra_fmu_dir
    new_log_entry = ChangeInfo(
        change_type=ChangeType.add,
        user="new_fmu_dir_user",
        path=Path("/some_new_path"),
        change="new change",
        hostname="new_host",
        file="config",
        key="new_test_key",
    )
    new_fmu_dir._changelog.add_log_entry(new_log_entry)
    assert len(new_fmu_dir._changelog.load()) == 1
    assert new_fmu_dir._changelog.load()[0] == new_log_entry

    dir_diff = fmu_dir.get_dir_diff(new_fmu_dir)

    expected_no_of_resources = 2
    assert len(dir_diff) == expected_no_of_resources
    assert dir_diff["config"] == []
    assert "_changelog" in dir_diff
    changelog_diff = dir_diff["_changelog"]

    assert len(changelog_diff) == 1
    assert changelog_diff[0][0] == "changelog"
    assert changelog_diff[0][1] is None
    assert isinstance(changelog_diff[0][2], Log)
    assert len(changelog_diff[0][2]) == 1
    assert changelog_diff[0][2].root[0] == new_log_entry


def test_fmu_directory_base_sync_dir_with_changelog(
    fmu_dir: ProjectFMUDirectory,
    extra_fmu_dir: ProjectFMUDirectory,
) -> None:
    """Tests syncing changelog with another .fmu directory."""
    log_entry = ChangeInfo(
        change_type=ChangeType.add,
        user="fmu_dir_user",
        path=Path("/some_path"),
        change="some change",
        hostname="host",
        file="config",
        key="test_key",
    )
    fmu_dir._changelog.add_log_entry(log_entry)
    assert len(fmu_dir._changelog.load()) == 1
    assert fmu_dir._changelog.load()[0] == log_entry

    new_fmu_dir = extra_fmu_dir
    new_log_entry = ChangeInfo(
        change_type=ChangeType.add,
        user="new_fmu_dir_user",
        path=Path("/some_new_path"),
        change="new change",
        hostname="new_host",
        file="config",
        key="new_test_key",
    )
    new_fmu_dir._changelog.add_log_entry(new_log_entry)
    assert len(new_fmu_dir._changelog.load()) == 1
    assert new_fmu_dir._changelog.load()[0] == new_log_entry

    updated_resources = fmu_dir.sync_dir(new_fmu_dir)

    assert len(updated_resources) == 1
    assert "_changelog" in updated_resources
    updated_changelog: Log[ChangeInfo] = updated_resources["_changelog"]
    expected_log_length = 3
    assert len(updated_changelog) == expected_log_length
    assert updated_changelog[0] == log_entry
    assert updated_changelog[1] == new_log_entry
    assert updated_changelog[2].change_type == ChangeType.merge
    assert "_changelog" in updated_changelog[2].change
    assert updated_changelog[2].path == fmu_dir.path


def test_fmu_directory_base_sync_dir_with_all_resources(
    fmu_dir: ProjectFMUDirectory,
    masterdata_dict: dict[str, Any],
    extra_fmu_dir: ProjectFMUDirectory,
) -> None:
    """Tests syncing with another .fmu directory with config, mappings and changelog."""
    assert fmu_dir.config.load().masterdata is None
    fmu_dir.set_config_value("masterdata", masterdata_dict)
    assert fmu_dir.config.load().masterdata is not None
    assert len(fmu_dir._changelog.load()) == 1
    assert fmu_dir._changelog.load()[0].change_type == ChangeType.update

    fmu_dir._mappings.update_stratigraphy_mappings(StratigraphyMappings(root=[]))
    new_fmu_dir = extra_fmu_dir
    new_strat_mapping = StratigraphyIdentifierMapping(
        source_system=DataSystem.rms,
        target_system=DataSystem.smda,
        relation_type=RelationType.primary,
        source_id="TopViking",
        target_id="VIKING GP. Top",
    )
    new_fmu_dir._mappings.update_stratigraphy_mappings(
        StratigraphyMappings(root=[new_strat_mapping])
    )

    assert len(new_fmu_dir._changelog.load()) == 1
    assert new_fmu_dir._changelog.load()[0].key == "stratigraphy"
    assert new_fmu_dir._changelog.load()[0].file == "mappings.json"

    updated_resources = fmu_dir.sync_dir(new_fmu_dir)

    expected_no_of_resources = 3
    assert len(updated_resources) == expected_no_of_resources
    assert "config" in updated_resources
    assert fmu_dir.config.load().masterdata is None

    assert "_mappings" in updated_resources
    assert len(fmu_dir._mappings.wellbore_mappings) == 0
    assert len(fmu_dir._mappings.stratigraphy_mappings) == 1
    assert fmu_dir._mappings.stratigraphy_mappings[0] == new_strat_mapping

    assert "_changelog" in updated_resources
    updated_changelog: Log[ChangeInfo] = updated_resources["_changelog"]
    expected_log_length = 6

    # Assert existing entries
    assert len(updated_changelog) == expected_log_length
    assert updated_changelog[0].key == "masterdata"
    assert updated_changelog[0].path == fmu_dir.path
    assert updated_changelog[1].key == "stratigraphy"
    assert updated_changelog[1].path == fmu_dir.path

    # Assert merged entry
    assert updated_changelog[2].key == "stratigraphy"
    assert updated_changelog[2].path == new_fmu_dir.path
    assert updated_changelog[2] == new_fmu_dir._changelog.load()[0]

    # Assert entries from merging config and mappings
    assert updated_changelog[3].key == "masterdata"
    assert updated_changelog[3].path == fmu_dir.path
    assert updated_changelog[4].key == "stratigraphy"
    assert updated_changelog[4].path == fmu_dir.path

    # Assert log entry with merge details
    assert updated_changelog[5].change_type == ChangeType.merge
    assert "config" in updated_changelog[5].file
    assert "_changelog" in updated_changelog[5].file
    assert "_mappings" in updated_changelog[5].file


def test_fmu_directory_base_sync_dir_dont_sync_ignored_fields(
    fmu_dir: ProjectFMUDirectory,
    extra_fmu_dir: ProjectFMUDirectory,
) -> None:
    """Tests that fields to be ignored are not synced.

    When syncing two .fmu directories, Pydantic resources with fields set
    to be ignored in a diff, should not be synced.
    """
    fmu_dir.set_config_value("cache_max_revisions", 5)
    created_at = fmu_dir.config.load().created_at
    created_by = fmu_dir.config.load().created_by
    last_modified_at = fmu_dir.config.load().last_modified_at
    last_modified_by = fmu_dir.config.load().last_modified_by

    new_fmu_dir = extra_fmu_dir
    new_cache_max_revisions = 10
    new_fmu_dir.set_config_value("cache_max_revisions", new_cache_max_revisions)

    updates = fmu_dir.sync_dir(new_fmu_dir)

    assert updates["config"].cache_max_revisions == new_cache_max_revisions

    # created_at and created_by should never change
    assert updates["config"].created_at == created_at
    assert updates["config"].created_by == created_by

    # last_modified_at changes when the config has been updated through the sync
    assert updates["config"].last_modified_at != last_modified_at
    assert updates["config"].last_modified_by == last_modified_by

    expected_log_length = 4
    assert len(updates["_changelog"]) == expected_log_length

    # First entry should be the cache_max_revision update in fmu_dir
    assert updates["_changelog"][0].key == "cache_max_revisions"
    assert "Old value: 5 -> New value: 5" in updates["_changelog"][0].change

    # Second entry should be the cache_max_revision update from the changelog merge
    assert updates["_changelog"][1].key == "cache_max_revisions"
    assert "Old value: 5 -> New value: 10" in updates["_changelog"][1].change
    assert updates["_changelog"][1].path == new_fmu_dir.path

    # Third entry should be the cache_max_revision update from the config merge
    assert updates["_changelog"][2].key == "cache_max_revisions"
    assert "Old value: 5 -> New value: 10" in updates["_changelog"][2].change
    assert updates["_changelog"][2].path == fmu_dir.path

    # Fourth entry should be the logged merge details
    assert updates["_changelog"][3].key == ".fmu"
    assert updates["_changelog"][3].change_type == ChangeType.merge

    # This should not happen, but just to illustrate:
    # Force updating one of the diff ignore fields, adds log entries that will be merged
    new_fmu_dir.set_config_value("created_by", "johndoe")
    updates = fmu_dir.sync_dir(new_fmu_dir)

    # The updated created_by value should not be merged
    assert new_fmu_dir.config.load().created_by == "johndoe"
    assert "config" not in updates
    assert fmu_dir.config.load().created_by != "johndoe"

    # The changelog entry for the update will be merged
    assert updates["_changelog"][4].key == "created_by"
    assert "Old value: user -> New value: johndoe" in updates["_changelog"][4].change


def test_fmu_directory_base_get_dir_diff_with_mappings(
    fmu_dir: ProjectFMUDirectory,
    extra_fmu_dir: ProjectFMUDirectory,
) -> None:
    """Tests getting the diff with another .fmu directory with mappings."""
    strat_mapping = StratigraphyIdentifierMapping(
        source_system=DataSystem.rms,
        target_system=DataSystem.smda,
        relation_type=RelationType.primary,
        source_id="TopViking",
        target_id="VIKING GP. Top",
    )
    fmu_dir._mappings.update_stratigraphy_mappings(
        StratigraphyMappings(root=[strat_mapping])
    )

    new_fmu_dir = extra_fmu_dir
    new_strat_mapping = copy.deepcopy(strat_mapping)
    new_strat_mapping.source_id = "TopVolantis"
    new_strat_mapping.target_id = "VOLANTIS GP. Top"
    new_fmu_dir._mappings.update_stratigraphy_mappings(
        StratigraphyMappings(root=[new_strat_mapping])
    )

    old_fmu_dir = copy.deepcopy(fmu_dir)
    dir_diff = fmu_dir.get_dir_diff(new_fmu_dir)

    # Assert no changes made to the .fmu directory
    assert fmu_dir.config.load() == old_fmu_dir.config.load()
    assert fmu_dir._changelog.load() == old_fmu_dir._changelog.load()
    assert fmu_dir._mappings.load() == old_fmu_dir._mappings.load()

    # Assert mappings diff is as expected
    assert "_mappings" in dir_diff
    assert len(dir_diff["_mappings"]) == 1
    mappings_diff = dir_diff["_mappings"][0]
    assert mappings_diff[0] == "mappings"
    assert mappings_diff[1] is None
    assert isinstance(mappings_diff[2], Mappings)
    assert len(mappings_diff[2].wellbore) == 0
    assert len(mappings_diff[2].stratigraphy) == 1
    assert mappings_diff[2].stratigraphy[0] == new_strat_mapping

    # Assert no config changes
    assert "config" in dir_diff
    assert len(dir_diff["config"]) == 0

    # Assert changelog diff has only the mappings update entry
    assert len(dir_diff["_changelog"]) == 1
    changelog_diff = dir_diff["_changelog"][0]
    assert changelog_diff[0] == "changelog"
    assert changelog_diff[1] is None
    assert len(changelog_diff[2]) == 1
    assert changelog_diff[2][0].key == "stratigraphy"
    assert changelog_diff[2][0].file == "mappings.json"


def test_fmu_directory_base_sync_dir_with_mappings(
    fmu_dir: ProjectFMUDirectory,
    extra_fmu_dir: ProjectFMUDirectory,
) -> None:
    """Tests syncing mappings resource with another .fmu directory."""
    strat_mapping = StratigraphyIdentifierMapping(
        source_system=DataSystem.rms,
        target_system=DataSystem.smda,
        relation_type=RelationType.primary,
        source_id="TopViking",
        target_id="VIKING GP. Top",
    )
    fmu_dir._mappings.update_stratigraphy_mappings(
        StratigraphyMappings(root=[strat_mapping])
    )

    new_fmu_dir = extra_fmu_dir
    new_strat_mapping = copy.deepcopy(strat_mapping)
    new_strat_mapping.source_id = "TopVolantis"
    new_strat_mapping.target_id = "VOLANTIS GP. Top"
    new_fmu_dir._mappings.update_stratigraphy_mappings(
        StratigraphyMappings(root=[new_strat_mapping])
    )

    updates = fmu_dir.sync_dir(new_fmu_dir)

    # Assert mappings are updated as expected
    assert "_mappings" in updates
    assert updates["_mappings"] == fmu_dir._mappings.load()
    assert len(fmu_dir._mappings.wellbore_mappings) == 0
    assert len(fmu_dir._mappings.stratigraphy_mappings) == 1
    assert fmu_dir._mappings.stratigraphy_mappings[0] == new_strat_mapping

    # Assert no config changes
    assert "config" not in updates

    # Assert changelog has all the mapping updates plus the merge entry
    changelog: Log[ChangeInfo] = updates["_changelog"]
    expected_log_length = 4
    assert len(changelog) == expected_log_length
    assert changelog[0].path == fmu_dir.path
    assert changelog[0].key == "stratigraphy"
    assert changelog[1].path == new_fmu_dir.path
    assert changelog[1].key == "stratigraphy"
    assert changelog[2].path == fmu_dir.path
    assert changelog[2].key == "stratigraphy"
    assert changelog[3].path == fmu_dir.path
    assert changelog[3].change_type == ChangeType.merge
    assert "mappings" in changelog[3].file
