"""Tests for pi_coding_agent.core.package_manager."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pi_coding_agent.core.package_manager import (
    DefaultPackageManager,
    PathMetadata,
    ProgressEvent,
    ResolvedPaths,
    ResolvedResource,
    _collect_files_by_extensions,
    _collect_skill_entries,
    _PackageManagerOptions,
    _sanitize_source_name,
    create_package_manager,
)

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def make_pm(tmp_path: Path) -> DefaultPackageManager:
    opts = _PackageManagerOptions(cwd=str(tmp_path), agent_dir=str(tmp_path / "agent"))
    return DefaultPackageManager(opts)


# ---------------------------------------------------------------------------
# Test sanitize_source_name
# ---------------------------------------------------------------------------


class TestSanitizeSourceName:
    def test_slashes_replaced(self) -> None:
        assert _sanitize_source_name("foo/bar") == "foo_bar"

    def test_at_sign_removed(self) -> None:
        assert _sanitize_source_name("@scope/pkg") == "scope_pkg"

    def test_colon_replaced(self) -> None:
        assert _sanitize_source_name("http:something") == "http_something"

    def test_simple_name_unchanged(self) -> None:
        assert _sanitize_source_name("mypackage") == "mypackage"


# ---------------------------------------------------------------------------
# Test create_package_manager factory
# ---------------------------------------------------------------------------


class TestCreatePackageManager:
    def test_returns_default_pm(self, tmp_path: Path) -> None:
        pm = create_package_manager(str(tmp_path), str(tmp_path / "agent"))
        assert isinstance(pm, DefaultPackageManager)


# ---------------------------------------------------------------------------
# Test _collect_files_by_extensions
# ---------------------------------------------------------------------------


class TestCollectFilesByExtensions:
    def test_collects_matching_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.md").write_text("hello")
        (tmp_path / "b.txt").write_text("world")
        result = _collect_files_by_extensions(str(tmp_path), (".md",))
        assert any("a.md" in p for p in result)
        assert not any("b.txt" in p for p in result)

    def test_skips_hidden_files(self, tmp_path: Path) -> None:
        (tmp_path / ".hidden.md").write_text("x")
        result = _collect_files_by_extensions(str(tmp_path), (".md",))
        assert not any(".hidden.md" in p for p in result)

    def test_skips_node_modules(self, tmp_path: Path) -> None:
        nm = tmp_path / "node_modules"
        nm.mkdir()
        (nm / "a.md").write_text("x")
        result = _collect_files_by_extensions(str(tmp_path), (".md",))
        assert not any("node_modules" in p for p in result)

    def test_nonexistent_directory_returns_empty(self) -> None:
        result = _collect_files_by_extensions("/nonexistent/path/xyz", (".md",))
        assert result == []

    def test_recursive_collection(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "deep.json").write_text("{}")
        result = _collect_files_by_extensions(str(tmp_path), (".json",))
        assert any("deep.json" in p for p in result)


# ---------------------------------------------------------------------------
# Test _collect_skill_entries
# ---------------------------------------------------------------------------


class TestCollectSkillEntries:
    def test_collects_root_md_files(self, tmp_path: Path) -> None:
        (tmp_path / "skill.md").write_text("# Skill")
        result = _collect_skill_entries(str(tmp_path))
        assert any("skill.md" in p for p in result)

    def test_collects_skill_md_in_subdirs(self, tmp_path: Path) -> None:
        sub = tmp_path / "my-skill"
        sub.mkdir()
        (sub / "SKILL.md").write_text("# My Skill")
        result = _collect_skill_entries(str(tmp_path))
        assert any("SKILL.md" in p for p in result)

    def test_ignores_non_skill_md_in_subdirs(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "README.md").write_text("readme")
        result = _collect_skill_entries(str(tmp_path))
        assert not any("README.md" in p for p in result)

    def test_skips_hidden_dirs(self, tmp_path: Path) -> None:
        hidden = tmp_path / ".hidden"
        hidden.mkdir()
        (hidden / "SKILL.md").write_text("x")
        result = _collect_skill_entries(str(tmp_path))
        assert not any(".hidden" in p for p in result)

    def test_nonexistent_directory_returns_empty(self) -> None:
        result = _collect_skill_entries("/nonexistent/path/xyz")
        assert result == []

    def test_include_root_files_false(self, tmp_path: Path) -> None:
        (tmp_path / "root.md").write_text("# Root")
        result = _collect_skill_entries(str(tmp_path), include_root_files=False)
        assert not any("root.md" in p for p in result)


# ---------------------------------------------------------------------------
# Test progress callback
# ---------------------------------------------------------------------------


class TestProgressCallback:
    def test_set_and_clear_callback(self, tmp_path: Path) -> None:
        pm = make_pm(tmp_path)
        events: list[ProgressEvent] = []
        pm.set_progress_callback(events.append)
        pm._emit_progress(ProgressEvent(type="start", action="install", source="pkg"))
        assert len(events) == 1
        pm.set_progress_callback(None)
        pm._emit_progress(ProgressEvent(type="complete", action="install", source="pkg"))
        assert len(events) == 1  # not incremented after clear


# ---------------------------------------------------------------------------
# Test get_installed_path
# ---------------------------------------------------------------------------


class TestGetInstalledPath:
    def test_user_scope_nonexistent(self, tmp_path: Path) -> None:
        pm = make_pm(tmp_path)
        result = pm.get_installed_path("my-pkg", "user")
        assert result is None

    def test_user_scope_exists(self, tmp_path: Path) -> None:
        agent_dir = tmp_path / "agent"
        pkg_dir = agent_dir / "packages" / "my-pkg"
        pkg_dir.mkdir(parents=True)
        pm = make_pm(tmp_path)
        result = pm.get_installed_path("my-pkg", "user")
        assert result is not None
        assert "my-pkg" in result

    def test_project_scope_nonexistent(self, tmp_path: Path) -> None:
        pm = make_pm(tmp_path)
        result = pm.get_installed_path("my-pkg", "project")
        assert result is None

    def test_project_scope_exists(self, tmp_path: Path) -> None:
        pkg_dir = tmp_path / ".pi" / "packages" / "my-pkg"
        pkg_dir.mkdir(parents=True)
        pm = make_pm(tmp_path)
        result = pm.get_installed_path("my-pkg", "project")
        assert result is not None


# ---------------------------------------------------------------------------
# Test add/remove source from settings
# ---------------------------------------------------------------------------


class TestSettingsManagement:
    def test_add_source_to_user_settings(self, tmp_path: Path) -> None:
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        pm = make_pm(tmp_path)
        result = pm.add_source_to_settings("my-pkg")
        assert result is True
        settings_path = agent_dir / "settings.json"
        assert settings_path.exists()
        data = json.loads(settings_path.read_text())
        assert "my-pkg" in data["packages"]

    def test_add_source_twice_returns_false(self, tmp_path: Path) -> None:
        (tmp_path / "agent").mkdir()
        pm = make_pm(tmp_path)
        pm.add_source_to_settings("my-pkg")
        result = pm.add_source_to_settings("my-pkg")
        assert result is False

    def test_remove_source_from_user_settings(self, tmp_path: Path) -> None:
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        pm = make_pm(tmp_path)
        pm.add_source_to_settings("my-pkg")
        result = pm.remove_source_from_settings("my-pkg")
        assert result is True
        settings_path = agent_dir / "settings.json"
        data = json.loads(settings_path.read_text())
        assert "my-pkg" not in data["packages"]

    def test_remove_nonexistent_source_returns_false(self, tmp_path: Path) -> None:
        (tmp_path / "agent").mkdir()
        pm = make_pm(tmp_path)
        result = pm.remove_source_from_settings("nonexistent")
        assert result is False

    def test_add_source_to_local_settings(self, tmp_path: Path) -> None:
        pm = make_pm(tmp_path)
        result = pm.add_source_to_settings("my-pkg", {"local": True})
        assert result is True
        settings_path = tmp_path / ".pi" / "settings.json"
        assert settings_path.exists()

    def test_remove_from_local_settings(self, tmp_path: Path) -> None:
        pm = make_pm(tmp_path)
        pm.add_source_to_settings("my-pkg", {"local": True})
        result = pm.remove_source_from_settings("my-pkg", {"local": True})
        assert result is True

    def test_malformed_settings_file_handled_gracefully(self, tmp_path: Path) -> None:
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        settings_path = agent_dir / "settings.json"
        settings_path.write_text("not valid json")
        pm = make_pm(tmp_path)
        result = pm.add_source_to_settings("my-pkg")
        assert result is True  # Treats malformed file as empty


# ---------------------------------------------------------------------------
# Test resolve
# ---------------------------------------------------------------------------


class TestResolve:
    @pytest.mark.anyio
    async def test_resolve_empty_dirs_returns_empty_paths(self, tmp_path: Path) -> None:
        pm = make_pm(tmp_path)
        result = await pm.resolve()
        assert isinstance(result, ResolvedPaths)
        assert result.skills == []
        assert result.prompts == []
        assert result.themes == []
        assert result.extensions == []

    @pytest.mark.anyio
    async def test_resolve_discovers_user_skills(self, tmp_path: Path) -> None:
        agent_dir = tmp_path / "agent"
        skills_dir = agent_dir / "skills"
        skills_dir.mkdir(parents=True)
        (skills_dir / "my-skill.md").write_text("# My Skill")
        pm = make_pm(tmp_path)
        result = await pm.resolve()
        assert len(result.skills) == 1
        assert "my-skill.md" in result.skills[0].path

    @pytest.mark.anyio
    async def test_resolve_discovers_project_skills(self, tmp_path: Path) -> None:
        skills_dir = tmp_path / ".pi" / "skills"
        skills_dir.mkdir(parents=True)
        (skills_dir / "proj-skill.md").write_text("# Proj Skill")
        pm = make_pm(tmp_path)
        result = await pm.resolve()
        assert any("proj-skill.md" in r.path for r in result.skills)

    @pytest.mark.anyio
    async def test_resolve_discovers_prompts(self, tmp_path: Path) -> None:
        agent_dir = tmp_path / "agent"
        prompts_dir = agent_dir / "prompts"
        prompts_dir.mkdir(parents=True)
        (prompts_dir / "my-prompt.md").write_text("prompt text")
        pm = make_pm(tmp_path)
        result = await pm.resolve()
        assert len(result.prompts) == 1

    @pytest.mark.anyio
    async def test_resolve_discovers_themes(self, tmp_path: Path) -> None:
        agent_dir = tmp_path / "agent"
        themes_dir = agent_dir / "themes"
        themes_dir.mkdir(parents=True)
        (themes_dir / "my-theme.json").write_text("{}")
        pm = make_pm(tmp_path)
        result = await pm.resolve()
        assert len(result.themes) == 1


# ---------------------------------------------------------------------------
# Test resolve_extension_sources
# ---------------------------------------------------------------------------


class TestResolveExtensionSources:
    @pytest.mark.anyio
    async def test_empty_sources_returns_empty(self, tmp_path: Path) -> None:
        pm = make_pm(tmp_path)
        result = await pm.resolve_extension_sources([])
        assert result.extensions == []

    @pytest.mark.anyio
    async def test_local_py_file_resolved(self, tmp_path: Path) -> None:
        ext_file = tmp_path / "myext.py"
        ext_file.write_text("# ext")
        pm = make_pm(tmp_path)
        result = await pm.resolve_extension_sources([str(ext_file)])
        assert len(result.extensions) == 1
        assert "myext.py" in result.extensions[0].path

    @pytest.mark.anyio
    async def test_directory_with_index_py_resolved(self, tmp_path: Path) -> None:
        ext_dir = tmp_path / "myext"
        ext_dir.mkdir()
        (ext_dir / "index.py").write_text("# index")
        pm = make_pm(tmp_path)
        result = await pm.resolve_extension_sources([str(ext_dir)])
        assert len(result.extensions) == 1
        assert "index.py" in result.extensions[0].path

    @pytest.mark.anyio
    async def test_nonexistent_source_skipped(self, tmp_path: Path) -> None:
        pm = make_pm(tmp_path)
        result = await pm.resolve_extension_sources(["/nonexistent/path/ext.py"])
        assert result.extensions == []


# ---------------------------------------------------------------------------
# Test dataclasses
# ---------------------------------------------------------------------------


class TestDataclasses:
    def test_path_metadata_defaults(self) -> None:
        meta = PathMetadata()
        assert meta.source == ""
        assert meta.scope == "user"
        assert meta.origin == "top-level"
        assert meta.base_dir is None

    def test_resolved_resource_defaults(self) -> None:
        res = ResolvedResource()
        assert res.path == ""
        assert res.enabled is True

    def test_progress_event_defaults(self) -> None:
        ev = ProgressEvent()
        assert ev.type == "start"
        assert ev.action == "install"
        assert ev.source == ""
        assert ev.message is None
