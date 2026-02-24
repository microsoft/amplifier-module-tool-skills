"""Tests for always including default skill directories.

When multiple bundle layers declare tool-skills with different config.skills
lists, only one config survives the merge. Default directories (workspace
.amplifier/skills/ and user ~/.amplifier/skills/) must always be scanned
as additional sources, not just as a fallback when no sources are configured.
"""

import os
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from amplifier_module_tool_skills import _resolve_skill_sources


def _make_skill(dir_path: Path, name: str, description: str = "Test skill") -> None:
    """Create a minimal valid skill in the given directory."""
    skill_dir = dir_path / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n# {name}\nContent"
    )


class FakeCoordinator:
    """Minimal coordinator stub for _resolve_skill_sources."""

    def __init__(self):
        self.config = {}

    def get_capability(self, name: str):
        return None


@pytest.mark.asyncio
async def test_default_dirs_included_when_explicit_sources_configured(
    tmp_path, monkeypatch
):
    """Default directories are appended even when config.skills provides explicit paths."""
    # Set up an explicit source directory with a skill
    explicit_dir = tmp_path / "explicit-skills"
    _make_skill(explicit_dir, "explicit-skill")

    # Set up a workspace .amplifier/skills directory with a different skill
    workspace_skills = tmp_path / "workspace" / ".amplifier" / "skills"
    _make_skill(workspace_skills, "workspace-skill")

    # Patch get_default_skills_dirs to return our tmp workspace path
    monkeypatch.setattr(
        "amplifier_module_tool_skills.get_default_skills_dirs",
        lambda: [workspace_skills],
    )

    config = {"skills": [str(explicit_dir)]}
    resolved = await _resolve_skill_sources(config, FakeCoordinator())

    resolved_strs = [str(p) for p in resolved]
    assert str(explicit_dir.resolve()) in resolved_strs, "Explicit source must be present"
    assert str(workspace_skills.resolve()) in resolved_strs, (
        "Default workspace dir must be appended even with explicit sources"
    )


@pytest.mark.asyncio
async def test_default_dirs_included_with_remote_sources(tmp_path, monkeypatch):
    """Default directories are appended even when config has remote git sources."""
    # Simulate a remote source resolving to a cached directory
    cached_dir = tmp_path / "cached-remote"
    _make_skill(cached_dir, "remote-skill")

    workspace_skills = tmp_path / "workspace" / ".amplifier" / "skills"
    _make_skill(workspace_skills, "workspace-skill")

    monkeypatch.setattr(
        "amplifier_module_tool_skills.get_default_skills_dirs",
        lambda: [workspace_skills],
    )

    # Patch is_remote_source to treat our test URL as remote
    monkeypatch.setattr(
        "amplifier_module_tool_skills.is_remote_source",
        lambda s: s.startswith("git+"),
    )

    # Patch resolve_skill_sources to return the cached dir
    async def mock_resolve(sources):
        return [cached_dir]

    monkeypatch.setattr(
        "amplifier_module_tool_skills.resolve_skill_sources",
        mock_resolve,
    )

    config = {"skills": ["git+https://github.com/example/skills@main"]}
    resolved = await _resolve_skill_sources(config, FakeCoordinator())

    resolved_strs = [str(p) for p in resolved]
    assert str(cached_dir) in resolved_strs, "Remote cached dir must be present"
    assert str(workspace_skills.resolve()) in resolved_strs, (
        "Default workspace dir must be appended even with remote sources"
    )


@pytest.mark.asyncio
async def test_default_dirs_not_duplicated(tmp_path, monkeypatch):
    """If a default dir is already in the explicit sources, don't add it twice."""
    workspace_skills = tmp_path / ".amplifier" / "skills"
    _make_skill(workspace_skills, "my-skill")

    monkeypatch.setattr(
        "amplifier_module_tool_skills.get_default_skills_dirs",
        lambda: [workspace_skills],
    )

    # Explicit config already points to the same directory
    config = {"skills": [str(workspace_skills)]}
    resolved = await _resolve_skill_sources(config, FakeCoordinator())

    # Should appear exactly once
    resolved_resolved = [p.resolve() for p in resolved]
    assert resolved_resolved.count(workspace_skills.resolve()) == 1


@pytest.mark.asyncio
async def test_nonexistent_default_dirs_skipped(tmp_path, monkeypatch):
    """Default directories that don't exist are not added."""
    explicit_dir = tmp_path / "explicit"
    _make_skill(explicit_dir, "a-skill")

    nonexistent = tmp_path / "does-not-exist"

    monkeypatch.setattr(
        "amplifier_module_tool_skills.get_default_skills_dirs",
        lambda: [nonexistent],
    )

    config = {"skills": [str(explicit_dir)]}
    resolved = await _resolve_skill_sources(config, FakeCoordinator())

    assert len(resolved) == 1
    assert str(explicit_dir.resolve()) in [str(p) for p in resolved]
