"""Tests for skill discovery."""

from pathlib import Path

import pytest
from amplifier_module_tool_skills.discovery import discover_skills
from amplifier_module_tool_skills.discovery import extract_skill_body
from amplifier_module_tool_skills.discovery import parse_skill_frontmatter


def test_parse_skill_frontmatter_valid():
    """Test parsing valid frontmatter."""
    content = """---
name: test-skill
description: Test skill description
version: 1.0.0
---
Body content"""

    test_file = Path("test.md")
    test_file.write_text(content)

    try:
        frontmatter = parse_skill_frontmatter(test_file)
        assert frontmatter is not None
        assert frontmatter["name"] == "test-skill"
        assert frontmatter["description"] == "Test skill description"
        assert frontmatter["version"] == "1.0.0"
    finally:
        test_file.unlink()


def test_parse_skill_frontmatter_no_frontmatter():
    """Test file without frontmatter."""
    content = "Just plain content"

    test_file = Path("test.md")
    test_file.write_text(content)

    try:
        frontmatter = parse_skill_frontmatter(test_file)
        assert frontmatter is None
    finally:
        test_file.unlink()


def test_extract_skill_body():
    """Test extracting markdown body."""
    content = """---
name: test-skill
description: Test
---

# Test Skill

Body content here"""

    test_file = Path("test.md")
    test_file.write_text(content)

    try:
        body = extract_skill_body(test_file)
        assert body is not None
        assert "# Test Skill" in body
        assert "Body content here" in body
        assert "---" not in body
    finally:
        test_file.unlink()


def test_discover_skills_fixture():
    """Test discovering skills from test fixtures."""
    fixtures_dir = Path(__file__).parent / "fixtures" / "skills"

    if not fixtures_dir.exists():
        pytest.skip("Fixtures directory not found")

    skills = discover_skills(fixtures_dir)

    # Should find our example skills
    assert len(skills) >= 1

    # Check that each skill has required fields
    for skill_name, metadata in skills.items():
        assert metadata.name == skill_name
        assert metadata.description
        assert metadata.path.exists()


def test_discover_skills_nonexistent():
    """Test discovering from non-existent directory."""
    skills = discover_skills(Path("/nonexistent/path"))
    assert len(skills) == 0


# ---------------------------------------------------------------------------
# Change 1: Cache-suffixed directories should not emit a warning
# ---------------------------------------------------------------------------


import logging
from tempfile import TemporaryDirectory


def test_no_warning_for_cache_suffixed_directory(caplog):
    """discover_skills must NOT warn when the directory name is a cache-suffix variant.

    sources.py creates directories like 'my-skill-f6de49e2167df367' for
    collision-safe remote skill caching.  discovery.py should tolerate them.
    """
    # 16 lowercase hex chars (as produced by sources.py)
    hex_suffix = "f6de49e2167df367"
    skill_name = "my-skill"
    cache_dir_name = f"{skill_name}-{hex_suffix}"  # e.g. "my-skill-f6de49e2167df367"

    with TemporaryDirectory() as tmpdir:
        parent = Path(tmpdir)
        skill_dir = parent / cache_dir_name
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {skill_name}\ndescription: Cached remote skill\n---\nContent\n"
        )

        with caplog.at_level(logging.WARNING, logger="amplifier_module_tool_skills.discovery"):
            skills = discover_skills(parent)

    assert skill_name in skills, "Skill should be discovered despite cache-suffixed dir"
    assert not any(
        "mismatched directory name" in record.message
        for record in caplog.records
    ), "No 'mismatched directory name' warning should be emitted for cache-suffixed dirs"
