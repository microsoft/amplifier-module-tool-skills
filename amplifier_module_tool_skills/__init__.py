"""
Amplifier tool for loading domain knowledge from skills.
Provides explicit skill discovery and loading capabilities.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from amplifier_core import ToolResult
from amplifier_module_tool_skills.discovery import discover_skills
from amplifier_module_tool_skills.discovery import discover_skills_multi_source
from amplifier_module_tool_skills.discovery import extract_skill_body
from amplifier_module_tool_skills.discovery import get_default_skills_dirs

if TYPE_CHECKING:
    from amplifier_core import ModuleCoordinator

logger = logging.getLogger(__name__)


async def mount(coordinator: "ModuleCoordinator", config: dict[str, Any] | None = None) -> None:
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
    description = """
Load domain knowledge from an available skill. Skills provide specialized knowledge, workflows, 
best practices, and standards. Use when you need domain expertise, coding guidelines, or 
architectural patterns.

Operations:

**List all skills:**
  load_skill(list=True)
  Returns a formatted list of all available skills with descriptions.

**Search for skills:**
  load_skill(search="pattern")
  Filters skills by name or description matching the search term.

**Get skill metadata:**
  load_skill(info="skill-name")
  Returns metadata (name, description, version, license, path) without loading full content.
  Use this to check details before loading or when you just need basic information.

**Load full skill content:**
  load_skill(skill_name="skill-name")
  Loads the complete skill content into context. Returns skill_directory path for accessing
  companion files referenced in the skill.

Usage Guidelines:
- Start tasks by listing or searching skills to discover relevant domain knowledge
- Use info operation to check skills before loading to conserve context
- Skills may reference companion files - use the returned skill_directory path with read_file tool
  Example: If skill returns skill_directory="/path/to/skill", you can read companion files with
  read_file(skill_directory + "/examples/code.py")
- Skills complement but don't replace documentation or web search - use for standardized workflows
  and best practices specific to the skill domain

Skill Discovery:
- Skills are discovered from configured directories (workspace, user, or custom paths)
- First-match-wins priority if same skill exists in multiple directories
- Workspace skills (.amplifier/skills/) override user skills (~/.amplifier/skills/)
"""

    def __init__(self, config: dict[str, Any], coordinator: "ModuleCoordinator | None" = None):
        """Initialize skills tool.
        
        Args:
            config: Tool configuration
            coordinator: Module coordinator for event emission (optional)
        """
        self.config = config
        self.coordinator = coordinator
        self.skills_dirs, self.skills = self._initialize_skills()

    def _initialize_skills(self) -> tuple[list[Path], dict[str, Any]]:
        """Initialize skills from config or defaults.
        
        Priority order:
        1. Config 'skills_dirs' or 'skills_dir'
        2. Default directories
        
        Returns:
            Tuple of (skills directories, discovered skills)
        """
        # Try config
        dirs = self._get_dirs_from_config()
        if dirs:
            skills = discover_skills_multi_source(dirs)
            logger.info(f"Discovered {len(skills)} skills from module config")
            return dirs, skills
        
        # Fall back to defaults
        dirs = get_default_skills_dirs()
        skills = discover_skills_multi_source(dirs)
        logger.info(f"Discovered {len(skills)} skills from default directories")
        return dirs, skills

    def _get_dirs_from_config(self) -> list[Path] | None:
        """Extract skills directories from config.
        
        Priority order:
        1. Module config (per-profile override)
        2. Global/project settings via coordinator.config
        3. None (falls back to defaults)
        
        Returns:
            List of paths if found in config, None otherwise
        """
        # 1. Check module-level config (per-profile override)
        if "skills_dirs" in self.config:
            dirs = self.config["skills_dirs"]
            if isinstance(dirs, str):
                dirs = [dirs]
            return [Path(d).expanduser() for d in dirs]
        
        if "skills_dir" in self.config:
            return [Path(self.config["skills_dir"]).expanduser()]
        
        # 2. Check global/project settings via coordinator
        if self.coordinator:
            global_config = self.coordinator.config.get('skills', {}).get('dirs')
            if global_config:
                if isinstance(global_config, str):
                    global_config = [global_config]
                logger.info(f"Using skills directories from settings: {global_config}")
                return [Path(d).expanduser() for d in global_config]
        
        # 3. Return None to use defaults
        return None

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

    async def execute(self, input: dict[str, Any]) -> ToolResult:
        """
        Execute skill tool operation.

        Args:
            input: Tool parameters

        Returns:
            Tool result with skill content or list
        """
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

    def _list_skills(self) -> ToolResult:
        """List all available skills."""
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

    def _search_skills(self, search_term: str) -> ToolResult:
        """Search skills by name or description."""
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

    def _get_skill_info(self, skill_name: str) -> ToolResult:
        """Get metadata for a skill without loading full content."""
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

    async def _load_skill(self, skill_name: str) -> ToolResult:
        """Load full skill content."""
        if skill_name not in self.skills:
            available = ", ".join(sorted(self.skills.keys()))
            return ToolResult(
                success=False, error={"message": f"Skill '{skill_name}' not found. Available: {available}"}
            )

        metadata = self.skills[skill_name]
        body = extract_skill_body(metadata.path)

        if not body:
            return ToolResult(success=False, error={"message": f"Failed to load content from {metadata.path}"})

        logger.info(f"Loaded skill: {skill_name}")

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
