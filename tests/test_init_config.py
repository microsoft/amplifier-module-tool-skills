"""Tests for _resolve_skill_sources config handling in __init__.py."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from amplifier_module_tool_skills import _resolve_skill_sources


class FakeCoordinator:
    """Minimal coordinator stub for testing."""

    def __init__(self):
        self.config = {}


# ---------------------------------------------------------------------------
# Change 2: cache_dir forwarded to resolve_skill_sources
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_dir_forwarded_to_resolve_skill_sources():
    """Config cache_dir must be passed through to resolve_skill_sources()."""
    coordinator = FakeCoordinator()
    config = {
        "skills": ["git+https://example.com/skills.git"],
        "cache_dir": "/tmp/my-custom-cache",
    }

    captured_kwargs: dict = {}

    async def fake_resolve(sources, cache_dir=None):
        captured_kwargs["cache_dir"] = cache_dir
        return []

    with patch(
        "amplifier_module_tool_skills.resolve_skill_sources",
        side_effect=fake_resolve,
    ):
        await _resolve_skill_sources(config, coordinator)

    assert captured_kwargs.get("cache_dir") == Path("/tmp/my-custom-cache"), (
        "cache_dir from config should be passed to resolve_skill_sources as a Path"
    )


# ---------------------------------------------------------------------------
# Change 3: skills_dirs additive when skills key present
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skills_dirs_additive_when_skills_present():
    """skills_dirs should be merged into sources even when 'skills' key is set."""
    coordinator = FakeCoordinator()

    with TemporaryDirectory() as tmpdir:
        extra_dir = Path(tmpdir)

        config = {
            "skills": ["git+https://example.com/skills.git"],
            "skills_dirs": str(extra_dir),
        }

        resolved_sources: list[str] = []

        async def fake_resolve(sources, cache_dir=None):
            resolved_sources.extend(sources)
            return []

        with patch(
            "amplifier_module_tool_skills.resolve_skill_sources",
            side_effect=fake_resolve,
        ):
            await _resolve_skill_sources(config, coordinator)

    # The extra_dir must appear alongside the git URL source
    assert str(extra_dir) in resolved_sources, (
        "skills_dirs path should be included even when 'skills' key is also present"
    )
    assert "git+https://example.com/skills.git" in resolved_sources, (
        "skills git URL should still be included"
    )
