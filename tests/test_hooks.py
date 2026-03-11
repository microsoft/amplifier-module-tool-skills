"""Tests for skills visibility hook."""

import pytest
from pathlib import Path
from amplifier_module_tool_skills.hooks import SkillsVisibilityHook
from amplifier_module_tool_skills.discovery import SkillMetadata


@pytest.fixture
def sample_skills():
    """Sample skills for testing."""
    return {
        "python-testing": SkillMetadata(
            name="python-testing",
            description="Best practices for Python testing with pytest",
            path=Path("/skills/python-testing/SKILL.md"),
            source="/skills",
        ),
        "git-workflow": SkillMetadata(
            name="git-workflow",
            description="Git branching and commit message standards",
            path=Path("/skills/git-workflow/SKILL.md"),
            source="/skills",
        ),
        "api-design": SkillMetadata(
            name="api-design",
            description="RESTful API design patterns and conventions",
            path=Path("/skills/api-design/SKILL.md"),
            source="/skills",
        ),
    }


@pytest.mark.asyncio
async def test_injects_skills_list(sample_skills):
    """Verify skills list is injected."""
    hook = SkillsVisibilityHook(sample_skills, {})
    result = await hook.on_provider_request("provider:request", {})

    assert result.action == "inject_context"
    assert result.context_injection is not None
    assert "<system-reminder" in result.context_injection
    assert "</system-reminder>" in result.context_injection
    assert "python-testing" in result.context_injection
    assert "git-workflow" in result.context_injection
    assert "api-design" in result.context_injection


@pytest.mark.asyncio
async def test_respects_enabled_flag(sample_skills):
    """Verify hook can be disabled."""
    hook = SkillsVisibilityHook(sample_skills, {"enabled": False})
    result = await hook.on_provider_request("provider:request", {})

    assert result.action == "continue"


@pytest.mark.asyncio
async def test_handles_empty_skills():
    """Verify graceful handling of no skills."""
    hook = SkillsVisibilityHook({}, {})
    result = await hook.on_provider_request("provider:request", {})

    assert result.action == "continue"


@pytest.mark.asyncio
async def test_limits_max_visible():
    """Verify max_skills_visible limit."""
    many_skills = {
        f"skill-{i:03d}": SkillMetadata(
            name=f"skill-{i:03d}",
            description=f"Test skill {i}",
            path=Path(f"/skills/skill-{i:03d}/SKILL.md"),
            source="/skills",
        )
        for i in range(100)
    }

    hook = SkillsVisibilityHook(many_skills, {"max_skills_visible": 10})
    result = await hook.on_provider_request("provider:request", {})

    assert result.action == "inject_context"
    assert "skill-000" in result.context_injection  # Should show first 10
    assert "(90 more" in result.context_injection  # Should show truncation
    assert "skill-050" not in result.context_injection  # Should not show beyond limit


@pytest.mark.asyncio
async def test_xml_boundaries_present(sample_skills):
    """Verify XML boundaries are properly formatted."""
    hook = SkillsVisibilityHook(sample_skills, {})
    result = await hook.on_provider_request("provider:request", {})

    content = result.context_injection
    assert content.startswith("<system-reminder")
    assert content.endswith("</system-reminder>")
    assert "Available skills (use load_skill tool):" in content


@pytest.mark.asyncio
async def test_configuration_options(sample_skills):
    """Verify configuration options are respected."""
    config = {
        "enabled": True,
        "inject_role": "system",
        "max_skills_visible": 2,
        "ephemeral": False,
        "priority": 15,
    }

    hook = SkillsVisibilityHook(sample_skills, config)
    result = await hook.on_provider_request("provider:request", {})

    assert result.action == "inject_context"
    assert result.context_injection_role == "system"
    assert result.ephemeral is False
    assert hook.priority == 15

    # Check that only 2 skills are shown
    lines = result.context_injection.split("\n")
    skill_lines = [line for line in lines if line.startswith("- **")]
    assert len(skill_lines) == 2


@pytest.mark.asyncio
async def test_default_configuration(sample_skills):
    """Verify default configuration values."""
    hook = SkillsVisibilityHook(sample_skills, {})

    assert hook.enabled is True
    assert hook.inject_role == "user"
    assert hook.max_visible == 50
    assert hook.ephemeral is True
    assert hook.priority == 20


@pytest.mark.asyncio
async def test_skills_sorted_alphabetically(sample_skills):
    """Verify skills are sorted alphabetically."""
    hook = SkillsVisibilityHook(sample_skills, {})
    result = await hook.on_provider_request("provider:request", {})

    content = result.context_injection
    lines = [line for line in content.split("\n") if line.startswith("- **")]

    # Extract skill names
    skill_names = []
    for line in lines:
        name = line.split("**")[1]
        skill_names.append(name)

    # Verify alphabetical order
    assert skill_names == sorted(skill_names)


@pytest.mark.asyncio
async def test_format_includes_descriptions(sample_skills):
    """Verify skill descriptions are included."""
    hook = SkillsVisibilityHook(sample_skills, {})
    result = await hook.on_provider_request("provider:request", {})

    content = result.context_injection
    assert "Best practices for Python testing with pytest" in content
    assert "Git branching and commit message standards" in content
    assert "RESTful API design patterns and conventions" in content


@pytest.mark.asyncio
async def test_single_skill():
    """Verify works with single skill."""
    single_skill = {
        "test-skill": SkillMetadata(
            name="test-skill",
            description="A test skill",
            path=Path("/skills/test-skill/SKILL.md"),
            source="/skills",
        )
    }

    hook = SkillsVisibilityHook(single_skill, {})
    result = await hook.on_provider_request("provider:request", {})

    assert result.action == "inject_context"
    assert "test-skill" in result.context_injection
    assert "A test skill" in result.context_injection
    # Should not show truncation message for single skill
    assert "more" not in result.context_injection


@pytest.mark.asyncio
async def test_ephemeral_flag_propagates(sample_skills):
    """Verify ephemeral flag is properly set in result."""
    # Test with ephemeral=True (default)
    hook_ephemeral = SkillsVisibilityHook(sample_skills, {"ephemeral": True})
    result_ephemeral = await hook_ephemeral.on_provider_request("provider:request", {})
    assert result_ephemeral.ephemeral is True

    # Test with ephemeral=False
    hook_persistent = SkillsVisibilityHook(sample_skills, {"ephemeral": False})
    result_persistent = await hook_persistent.on_provider_request(
        "provider:request", {}
    )
    assert result_persistent.ephemeral is False


@pytest.mark.asyncio
async def test_skips_injection_for_sub_agent_session(sample_skills):
    """Verify skills are NOT injected for sub-agent sessions (those with parent_id).

    Sub-agents should use load_skill() explicitly rather than receiving the full
    skills list on every turn — reduces compaction pressure in nested sessions.
    See: microsoft-amplifier/amplifier-support#136
    """
    hook = SkillsVisibilityHook(sample_skills, {})

    # Sub-agent: session dict contains a parent_id
    sub_agent_data = {"session": {"parent_id": "610b6186-079f-4f9a-acbe-2f2c5e68e6a7"}}
    result = await hook.on_provider_request("provider:request", sub_agent_data)

    assert result.action == "continue", "Sub-agent session should skip skills injection"


@pytest.mark.asyncio
async def test_injects_for_root_session_without_parent_id(sample_skills):
    """Verify skills ARE injected for root sessions (no parent_id).

    Root sessions should still receive the skills list as normal.
    """
    hook = SkillsVisibilityHook(sample_skills, {})

    # Root session: no parent_id in session dict
    root_data = {"session": {"id": "some-root-session-id"}}
    result = await hook.on_provider_request("provider:request", root_data)

    assert result.action == "inject_context"
    assert "python-testing" in result.context_injection


@pytest.mark.asyncio
async def test_injects_when_no_session_key(sample_skills):
    """Verify skills ARE injected when data has no session key at all (legacy/unknown callers)."""
    hook = SkillsVisibilityHook(sample_skills, {})

    # No session key — treat as root session (safe default)
    result = await hook.on_provider_request("provider:request", {})

    assert result.action == "inject_context"
