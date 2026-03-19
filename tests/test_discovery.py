"""Tests for skill discovery."""

import os
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


def test_discover_skills_through_symlink(tmp_path: Path):
    """Skill directories that are symlinks must be traversed.

    Python 3.13 changed Path.glob() to not follow symlinks by default.
    This test ensures discover_skills() finds skills inside symlinked
    subdirectories on all supported Python versions.
    """
    # Create the canonical skill location outside the scan directory
    canonical = tmp_path / "canonical" / "my-skill"
    canonical.mkdir(parents=True)
    (canonical / "SKILL.md").write_text(
        "---\nname: my-skill\ndescription: A symlinked skill\n---\nBody\n"
    )

    # Create the scan directory with a symlink to the canonical location
    scan_dir = tmp_path / "skills"
    scan_dir.mkdir()
    os.symlink(canonical, scan_dir / "my-skill")

    skills = discover_skills(scan_dir)
    assert "my-skill" in skills, (
        f"Skill in symlinked directory not discovered. Found: {list(skills.keys())}"
    )
