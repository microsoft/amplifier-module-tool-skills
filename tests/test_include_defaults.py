"""Tests for include_defaults config option in _resolve_skill_sources."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from amplifier_module_tool_skills import _resolve_skill_sources


class FakeCoordinator:
    """Minimal coordinator stub."""

    def __init__(self):
        self.config = {}


@pytest.mark.asyncio
async def test_include_defaults_false_by_default():
    """When include_defaults is not set, defaults are NOT appended to configured sources."""
    coordinator = FakeCoordinator()

    with TemporaryDirectory() as tmpdir:
        # Create a local skill source
        source_dir = Path(tmpdir) / "explicit-skills"
        source_dir.mkdir()

        config = {"skills": [str(source_dir)]}

        # Create a fake default dir that would be found if defaults were included
        default_dir = Path(tmpdir) / "default-skills"
        default_dir.mkdir()

        with patch(
            "amplifier_module_tool_skills.get_default_skills_dirs",
            return_value=[default_dir],
        ):
            result = await _resolve_skill_sources(config, coordinator)

        # Only the explicit source should be present
        assert source_dir.resolve() in result
        assert default_dir not in result


@pytest.mark.asyncio
async def test_include_defaults_true_appends_default_dirs():
    """When include_defaults is True, default dirs are appended after configured sources."""
    coordinator = FakeCoordinator()

    with TemporaryDirectory() as tmpdir:
        # Create a local skill source
        source_dir = Path(tmpdir) / "explicit-skills"
        source_dir.mkdir()

        # Create a default dir
        default_dir = Path(tmpdir) / "default-skills"
        default_dir.mkdir()

        config = {
            "skills": [str(source_dir)],
            "include_defaults": True,
        }

        with patch(
            "amplifier_module_tool_skills.get_default_skills_dirs",
            return_value=[default_dir],
        ):
            result = await _resolve_skill_sources(config, coordinator)

        # Both the explicit source and the default dir should be present
        assert source_dir.resolve() in result
        assert default_dir.resolve() in result


@pytest.mark.asyncio
async def test_include_defaults_true_with_remote_sources():
    """When include_defaults is True with remote sources, defaults are appended after resolution."""
    coordinator = FakeCoordinator()

    with TemporaryDirectory() as tmpdir:
        # Create a default dir
        default_dir = Path(tmpdir) / "default-skills"
        default_dir.mkdir()

        # Simulate a remote resolved dir
        remote_resolved = Path(tmpdir) / "remote-resolved"
        remote_resolved.mkdir()

        config = {
            "skills": ["git+https://github.com/example/skills@main"],
            "include_defaults": True,
        }

        with (
            patch(
                "amplifier_module_tool_skills.resolve_skill_sources",
                return_value=[remote_resolved],
            ),
            patch(
                "amplifier_module_tool_skills.get_default_skills_dirs",
                return_value=[default_dir],
            ),
        ):
            result = await _resolve_skill_sources(config, coordinator)

        # Remote resolved dir comes first, then default dir
        assert result[0] == remote_resolved
        assert default_dir.resolve() in result


@pytest.mark.asyncio
async def test_include_defaults_deduplicates():
    """When a default dir is already in configured sources, it is not added twice."""
    coordinator = FakeCoordinator()

    with TemporaryDirectory() as tmpdir:
        # Use the same dir as both explicit source and default
        shared_dir = Path(tmpdir) / "shared-skills"
        shared_dir.mkdir()

        config = {
            "skills": [str(shared_dir)],
            "include_defaults": True,
        }

        with patch(
            "amplifier_module_tool_skills.get_default_skills_dirs",
            return_value=[shared_dir],
        ):
            result = await _resolve_skill_sources(config, coordinator)

        # Should appear exactly once
        resolved_shared = shared_dir.resolve()
        assert result.count(resolved_shared) == 1


@pytest.mark.asyncio
async def test_include_defaults_skips_nonexistent():
    """Default dirs that don't exist on disk are not appended."""
    coordinator = FakeCoordinator()

    with TemporaryDirectory() as tmpdir:
        source_dir = Path(tmpdir) / "explicit-skills"
        source_dir.mkdir()

        nonexistent = Path(tmpdir) / "does-not-exist"

        config = {
            "skills": [str(source_dir)],
            "include_defaults": True,
        }

        with patch(
            "amplifier_module_tool_skills.get_default_skills_dirs",
            return_value=[nonexistent],
        ):
            result = await _resolve_skill_sources(config, coordinator)

        # Only the explicit source, not the nonexistent default
        assert source_dir.resolve() in result
        assert len(result) == 1
