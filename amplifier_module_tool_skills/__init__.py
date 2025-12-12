"""
Amplifier tool for loading domain knowledge from skills.
Provides explicit skill discovery and loading capabilities.
"""

import logging
from pathlib import Path
from typing import Any

from amplifier_module_tool_skills.discovery import discover_skills
from amplifier_module_tool_skills.discovery import discover_skills_multi_source
from amplifier_module_tool_skills.discovery import extract_skill_body
from amplifier_module_tool_skills.discovery import get_default_skills_dirs

logger = logging.getLogger(__name__)


async def mount(coordinator: Any, config: dict[str, Any] | None = None) -> None:
    """
    Mount the skills tool.

    Args:
        coordinator: Module coordinator
        config: Tool configuration

    Returns:
        Optional cleanup function
    """
    config = config or {}
    logger.info(f"Mounting SkillsTool with config: {config}")
    
    # Declare observable events for hooks-logging auto-discovery
    obs_events = coordinator.get_capability("observability.events") or []
    obs_events.extend([
        "skills:discovered",  # When skills are found during mount
        "skill:loaded",       # When skill loaded successfully
    ])
    coordinator.register_capability("observability.events", obs_events)
    
    tool = SkillsTool(config, coordinator)
    await coordinator.mount("tools", tool, name=tool.name)
    logger.info(f"Mounted SkillsTool with {len(tool.skills)} skills from {len(tool.skills_dirs)} sources")

    # Emit discovery event
    await coordinator.hooks.emit(
        "skills:discovered",
        {
            "skill_count": len(tool.skills),
            "skill_names": list(tool.skills.keys()),
            "sources": [str(d) for d in tool.skills_dirs],
        },
    )

    return


class SkillsTool:
    """Tool for loading domain knowledge from skills."""

    name = "load_skill"
    description = (
        "Load domain knowledge from an available skill. Skills provide "
        "specialized knowledge, workflows, best practices, and standards. "
        "Use when you need domain expertise, coding guidelines, or "
        "architectural patterns. Call with list=true to see all skills. "
        "When loaded, returns skill_directory path - use this to read companion "
        "files referenced in the skill (e.g., skill_directory + '/reference/file.md')."
    )

    def __init__(self, config: dict[str, Any], coordinator: Any | None = None):
        """
        Initialize skills tool.

        Args:
            config: Tool configuration
            coordinator: Module coordinator for event emission (optional)
        """
        self.config = config
        self.coordinator = coordinator

        # Try to use skills from context-skills capability first
        skills_from_context = coordinator.get_capability("skills.registry") if coordinator else None
        skills_dirs_from_context = coordinator.get_capability("skills.directories") if coordinator else None

        if skills_from_context and skills_dirs_from_context:
            # Reuse discovery from context-skills module
            self.skills = skills_from_context
            self.skills_dirs = skills_dirs_from_context
            logger.info(
                f"Using skills from context capability: {len(self.skills)} skills from {len(self.skills_dirs)} directories"
            )
        elif "skills_dirs" in config:
            # Fall back to own configuration
            skills_dirs = config["skills_dirs"]
            if isinstance(skills_dirs, str):
                skills_dirs = [skills_dirs]
            self.skills_dirs = [Path(d).expanduser() for d in skills_dirs]
            self.skills = discover_skills_multi_source(self.skills_dirs)
            logger.info(f"Discovered {len(self.skills)} skills from module config")
        elif "skills_dir" in config:
            # Single directory from config
            self.skills_dirs = [Path(config["skills_dir"]).expanduser()]
            self.skills = discover_skills(self.skills_dirs[0])
            logger.info(f"Discovered {len(self.skills)} skills from module config")
        else:
            # Fall back to default
            self.skills_dirs = get_default_skills_dirs()
            self.skills = discover_skills_multi_source(self.skills_dirs)
            logger.info(f"Discovered {len(self.skills)} skills from default directories")

    @property
    def input_schema(self) -> dict:
        """Return JSON schema for tool parameters."""
        return {
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "description": "Name of skill to load (e.g., 'design-patterns', 'python-standards')",
                },
                "list": {"type": "boolean", "description": "If true, return list of all available skills"},
                "search": {"type": "string", "description": "Search term to filter skills by name or description"},
                "info": {
                    "type": "string",
                    "description": "Get metadata for a specific skill without loading full content",
                },
            },
        }

    async def execute(self, input: dict[str, Any]) -> Any:
        """
        Execute skill tool operation.

        Args:
            input: Tool parameters

        Returns:
            Tool result with skill content or list
        """
        # Import here to avoid circular dependency
        from amplifier_core import ToolResult

        # List mode
        if input.get("list"):
            return self._list_skills()

        # Search mode
        if search_term := input.get("search"):
            return self._search_skills(search_term)

        # Info mode
        if skill_name := input.get("info"):
            return self._get_skill_info(skill_name)

        # Load mode
        skill_name = input.get("skill_name")
        if not skill_name:
            return ToolResult(
                success=False, error={"message": "Must provide skill_name, list=true, search='term', or info='name'"}
            )

        return await self._load_skill(skill_name)

    def _list_skills(self) -> Any:
        """List all available skills."""
        from amplifier_core import ToolResult

        if not self.skills:
            sources = ", ".join(str(d) for d in self.skills_dirs)
            return ToolResult(success=True, output={"message": f"No skills found in {sources}"})

        skills_list = []
        for name, metadata in sorted(self.skills.items()):
            skills_list.append({"name": name, "description": metadata.description})

        lines = ["Available Skills:", ""]
        for skill in skills_list:
            lines.append(f"**{skill['name']}**: {skill['description']}")

        return ToolResult(success=True, output={"message": "\n".join(lines), "skills": skills_list})

    def _search_skills(self, search_term: str) -> Any:
        """Search skills by name or description."""
        from amplifier_core import ToolResult

        matches = {}
        for name, metadata in self.skills.items():
            if search_term.lower() in name.lower() or search_term.lower() in metadata.description.lower():
                matches[name] = metadata

        if not matches:
            return ToolResult(success=True, output={"message": f"No skills matching '{search_term}'"})

        lines = [f"Skills matching '{search_term}':", ""]
        results = []
        for name, metadata in sorted(matches.items()):
            lines.append(f"**{name}**: {metadata.description}")
            results.append({"name": name, "description": metadata.description})

        return ToolResult(success=True, output={"message": "\n".join(lines), "matches": results})

    def _get_skill_info(self, skill_name: str) -> Any:
        """Get metadata for a skill without loading full content."""
        from amplifier_core import ToolResult

        if skill_name not in self.skills:
            available = ", ".join(sorted(self.skills.keys()))
            return ToolResult(
                success=False, error={"message": f"Skill '{skill_name}' not found. Available: {available}"}
            )

        metadata = self.skills[skill_name]
        info = {
            "name": metadata.name,
            "description": metadata.description,
            "version": metadata.version,
            "license": metadata.license,
            "path": str(metadata.path),
        }

        if metadata.metadata:
            info["metadata"] = metadata.metadata

        return ToolResult(success=True, output=info)

    async def _load_skill(self, skill_name: str) -> Any:
        """Load full skill content."""
        from amplifier_core import ToolResult

        if skill_name not in self.skills:
            available = ", ".join(sorted(self.skills.keys()))
            return ToolResult(
                success=False, error={"message": f"Skill '{skill_name}' not found. Available: {available}"}
            )

        # Check context if available
        if self.coordinator:
            context = self.coordinator.get("context")
            if context and hasattr(context, "is_skill_loaded"):
                # Check if already loaded
                if context.is_skill_loaded(skill_name):
                    return ToolResult(
                        success=True,
                        output={
                            "message": f"Skill '{skill_name}' is already loaded in context",
                            "skill_name": skill_name,
                            "already_loaded": True,
                        },
                    )

                # Check if can load another skill
                if hasattr(context, "can_load_skill"):
                    can_load, warning = context.can_load_skill()
                    if not can_load:
                        return ToolResult(success=False, error={"message": warning or "Cannot load more skills"})

                    if warning:
                        logger.warning(warning)

        metadata = self.skills[skill_name]
        body = extract_skill_body(metadata.path)

        if not body:
            return ToolResult(success=False, error={"message": f"Failed to load content from {metadata.path}"})

        logger.info(f"Loaded skill: {skill_name}")

        # Mark as loaded in context if available
        if self.coordinator:
            context = self.coordinator.get("context")
            if context and hasattr(context, "mark_skill_loaded"):
                context.mark_skill_loaded(skill_name)

        # Emit skill loaded event
        if self.coordinator:
            await self.coordinator.hooks.emit(
                "skill:loaded",
                {
                    "skill_name": skill_name,
                    "source": metadata.source,
                    "content_length": len(body),
                    "version": metadata.version,
                },
            )

        return ToolResult(
            success=True,
            output={
                "content": f"# {skill_name}\n\n{body}",
                "skill_name": skill_name,
                "skill_directory": str(metadata.path.parent),  # Actual skill folder for companion files
                "loaded_from": metadata.source,  # Source directory for context
            },
        )
