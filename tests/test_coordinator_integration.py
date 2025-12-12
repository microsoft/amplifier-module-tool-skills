"""Tests for coordinator integration and observability."""

import pytest
from pathlib import Path
from amplifier_module_tool_skills import mount, SkillsTool


class MockCoordinator:
    """Mock coordinator for testing."""
    
    def __init__(self):
        self.capabilities = {}
        self.mounted_tools = {}
        self.hooks = MockHooks()
        
    def register_capability(self, name: str, value):
        """Register a capability."""
        self.capabilities[name] = value
        
    def get_capability(self, name: str):
        """Get a capability."""
        return self.capabilities.get(name)
    
    def get(self, name: str):
        """Get a component."""
        return None
    
    async def mount(self, category: str, tool, name: str):
        """Mount a tool."""
        self.mounted_tools[name] = tool


class MockHooks:
    """Mock hooks system for testing."""
    
    def __init__(self):
        self.listeners = {}
        self.emitted_events = []
        
    def on(self, event_name: str, listener):
        """Register event listener."""
        if event_name not in self.listeners:
            self.listeners[event_name] = []
        self.listeners[event_name].append(listener)
        
    async def emit(self, event_name: str, data):
        """Emit an event."""
        self.emitted_events.append((event_name, data))
        # Call listeners
        if event_name in self.listeners:
            for listener in self.listeners[event_name]:
                await listener(event_name, data)


@pytest.mark.asyncio
async def test_mount_registers_observable_events():
    """Test that mount registers observable events for hooks-logging."""
    coordinator = MockCoordinator()
    config = {}
    
    await mount(coordinator, config)
    
    # Verify events registered in capability
    obs_events = coordinator.get_capability("observability.events")
    assert obs_events is not None
    assert "skills:discovered" in obs_events
    assert "skill:loaded" in obs_events


@pytest.mark.asyncio
async def test_mount_emits_discovery_event(tmp_path):
    """Test that mount emits skills:discovered event."""
    coordinator = MockCoordinator()
    
    # Create test skill
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("""---
name: test-skill
description: Test skill
---
# Test""")
    
    config = {"skills_dir": str(tmp_path)}
    
    # Track emitted events
    emitted_events = []
    async def event_listener(event_name, data):
        emitted_events.append((event_name, data))
    
    coordinator.hooks.on("skills:discovered", event_listener)
    
    await mount(coordinator, config)
    
    # Verify event emitted
    assert len(emitted_events) == 1
    event_name, data = emitted_events[0]
    assert event_name == "skills:discovered"
    assert data["skill_count"] == 1
    assert "test-skill" in data["skill_names"]


@pytest.mark.asyncio
async def test_load_skill_emits_event(tmp_path):
    """Test that loading skill emits skill:loaded event."""
    coordinator = MockCoordinator()
    
    # Create test skill
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("""---
name: test-skill
description: Test skill
version: 1.0.0
---
# Test Content""")
    
    tool = SkillsTool({"skills_dir": str(tmp_path)}, coordinator)
    
    # Track emitted events
    emitted_events = []
    async def event_listener(event_name, data):
        emitted_events.append((event_name, data))
    
    coordinator.hooks.on("skill:loaded", event_listener)
    
    result = await tool.execute({"skill_name": "test-skill"})
    
    # Verify success
    assert result.success is True
    
    # Verify event emitted
    assert len(emitted_events) == 1
    event_name, data = emitted_events[0]
    assert event_name == "skill:loaded"
    assert data["skill_name"] == "test-skill"
    assert data["version"] == "1.0.0"
    assert "content_length" in data


@pytest.mark.asyncio
async def test_capability_reuse(tmp_path):
    """Test that tool reuses skills from capability registry."""
    coordinator = MockCoordinator()
    
    # Pre-register skills capability
    from amplifier_module_tool_skills.discovery import SkillMetadata
    test_skills = {
        "cached-skill": SkillMetadata(
            name="cached-skill",
            description="From capability",
            path=Path("/fake/path"),
            source="capability"
        )
    }
    test_dirs = [tmp_path]
    
    coordinator.register_capability("skills.registry", test_skills)
    coordinator.register_capability("skills.directories", test_dirs)
    
    tool = SkillsTool({}, coordinator)
    
    # Should reuse capability, not discover again
    assert tool.skills == test_skills
    assert tool.skills_dirs == test_dirs


@pytest.mark.asyncio
async def test_event_aggregation():
    """Test that event declaration uses aggregation pattern."""
    coordinator = MockCoordinator()
    
    # Pre-register some events
    coordinator.register_capability("observability.events", ["existing:event"])
    
    await mount(coordinator, {})
    
    # Verify events were aggregated, not replaced
    obs_events = coordinator.get_capability("observability.events")
    assert "existing:event" in obs_events
    assert "skills:discovered" in obs_events
    assert "skill:loaded" in obs_events


@pytest.mark.asyncio
async def test_mount_without_config():
    """Test that mount works with None config."""
    coordinator = MockCoordinator()
    
    await mount(coordinator, None)
    
    # Should still register events
    obs_events = coordinator.get_capability("observability.events")
    assert obs_events is not None
    assert "skills:discovered" in obs_events


@pytest.mark.asyncio
async def test_tool_without_coordinator():
    """Test that tool works without coordinator."""
    # Tool should still work without coordinator
    tool = SkillsTool({}, None)
    
    # Should have initialized with defaults
    assert tool.skills is not None
    assert tool.skills_dirs is not None


@pytest.mark.asyncio
async def test_event_data_structure(tmp_path):
    """Test that emitted events have correct data structure."""
    coordinator = MockCoordinator()
    
    # Create test skill
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("""---
name: test-skill
description: Test skill
version: 2.1.0
license: MIT
---
# Test Content Here""")
    
    config = {"skills_dir": str(tmp_path)}
    
    await mount(coordinator, config)
    
    # Check discovery event structure
    discovery_events = [e for e in coordinator.hooks.emitted_events if e[0] == "skills:discovered"]
    assert len(discovery_events) == 1
    _, discovery_data = discovery_events[0]
    
    assert "skill_count" in discovery_data
    assert "skill_names" in discovery_data
    assert "sources" in discovery_data
    assert isinstance(discovery_data["skill_count"], int)
    assert isinstance(discovery_data["skill_names"], list)
    assert isinstance(discovery_data["sources"], list)
    
    # Load skill and check loaded event structure
    tool = coordinator.mounted_tools["load_skill"]
    result = await tool.execute({"skill_name": "test-skill"})
    assert result.success
    
    loaded_events = [e for e in coordinator.hooks.emitted_events if e[0] == "skill:loaded"]
    assert len(loaded_events) == 1
    _, loaded_data = loaded_events[0]
    
    assert "skill_name" in loaded_data
    assert "source" in loaded_data
    assert "content_length" in loaded_data
    assert "version" in loaded_data
    assert loaded_data["skill_name"] == "test-skill"
    assert loaded_data["version"] == "2.1.0"
    assert loaded_data["content_length"] > 0


@pytest.mark.asyncio
async def test_multiple_skills_discovery(tmp_path):
    """Test discovery event with multiple skills."""
    coordinator = MockCoordinator()
    
    # Create multiple test skills
    for i in range(3):
        skill_dir = tmp_path / f"skill-{i}"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(f"""---
name: skill-{i}
description: Test skill {i}
---
# Test""")
    
    config = {"skills_dir": str(tmp_path)}
    
    await mount(coordinator, config)
    
    # Verify event has correct count
    discovery_events = [e for e in coordinator.hooks.emitted_events if e[0] == "skills:discovered"]
    assert len(discovery_events) == 1
    _, data = discovery_events[0]
    
    assert data["skill_count"] == 3
    assert len(data["skill_names"]) == 3
    assert all(f"skill-{i}" in data["skill_names"] for i in range(3))
