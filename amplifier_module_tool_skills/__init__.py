"""Amplifier tool for loading domain knowledge from skills.

Provides explicit skill discovery and loading capabilities.
Supports local directories and git URL sources for skills.
"""

from __future__ import annotations

import logging
from pathlib import Path
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

from amplifier_core import ToolResult

from amplifier_module_tool_skills.discovery import discover_skills
from amplifier_module_tool_skills.discovery import discover_skills_multi_source
from amplifier_module_tool_skills.discovery import extract_skill_body
from amplifier_module_tool_skills.discovery import get_default_skills_dirs
from amplifier_module_tool_skills.sources import is_remote_source
from amplifier_module_tool_skills.sources import resolve_skill_source
from amplifier_module_tool_skills.sources import resolve_skill_sources

if TYPE_CHECKING:
    from amplifier_core import ModuleCoordinator

logger = logging.getLogger(__name__)


async def _resolve_skill_sources(
    config: dict[str, Any], coordinator: "ModuleCoordinator"
) -> list[Path]:
    """Resolve skill sources from config, handling both local paths and git URLs.

    Priority order:
    1. 'skills' config (new format - supports git URLs)
    2. 'skills_dirs' config (legacy - local paths only)
    3. 'skills_dir' config (legacy - single local path)
    4. Global settings via coordinator.config
    5. Default directories

    Args:
        config: Tool configuration dict.
        coordinator: Module coordinator for accessing global config.

    Returns:
        List of resolved local directory paths.
    """
    sources: list[str] = []

    # 1. Check 'skills' config (new format - supports git URLs)
    if "skills" in config:
        skills_config = config["skills"]
        if isinstance(skills_config, str):
            sources = [skills_config]
        elif isinstance(skills_config, list):
            sources = list(skills_config)

    # 2. Check 'skills_dirs' config (local directories).
    # When 'skills' is present, skills_dirs is ADDITIVE (not exclusive).
    # This allows git URL sources + local directory sources to coexist.
    if "skills_dirs" in config:
        dirs = config["skills_dirs"]
        extra = [dirs] if isinstance(dirs, str) else list(dirs)
        for d in extra:
            if d not in sources:
                sources.append(d)

    # 3. Check legacy 'skills_dir' config (kept for backward compat, not additive)
    elif not sources and "skills_dir" in config:
        sources = [config["skills_dir"]]

    # 4. Check global/project settings via coordinator
    elif coordinator:
        global_skills = coordinator.config.get("skills", {})
        if isinstance(global_skills, list):
            # Direct list format: skills: [url1, url2, ...]
            sources = list(global_skills)
        elif isinstance(global_skills, dict):
            # Dict format: skills: {sources: [...]} or skills: {dirs: [...]}
            if "sources" in global_skills:
                src = global_skills["sources"]
                sources = [src] if isinstance(src, str) else list(src)
            elif "dirs" in global_skills:
                dirs = global_skills["dirs"]
                sources = [dirs] if isinstance(dirs, str) else list(dirs)

    # 5. Fall back to defaults if no sources configured
    if not sources:
        logger.debug("No skill sources configured, using defaults")
        return get_default_skills_dirs()

    # Check if any sources are remote (need async resolution)
    has_remote = any(is_remote_source(s) for s in sources)

    if has_remote:
        # Resolve all sources (handles both local and remote)
        logger.info(f"Resolving {len(sources)} skill sources (includes remote)")
        cache_dir = config.get("cache_dir")
        cache_path = Path(cache_dir).expanduser() if cache_dir else None
        return await resolve_skill_sources(sources, cache_dir=cache_path)
    else:
        # All local - just expand paths
        resolved = []
        for source in sources:
            path = Path(source).expanduser().resolve()
            if path.exists():
                resolved.append(path)
            else:
                logger.debug(f"Local skill source does not exist: {path}")
        return resolved if resolved else get_default_skills_dirs()


async def mount(
    coordinator: "ModuleCoordinator", config: dict[str, Any] | None = None
) -> Callable[[], Coroutine[Any, Any, None]] | None:
    """Mount the skills tool.

    Args:
        coordinator: Module coordinator
        config: Tool configuration

    Configuration options:
        skills: List of skill sources (local paths or git URLs)
            Example: ["~/.amplifier/skills", "git+https://github.com/org/skills@main"]
        skills_dirs: Legacy alias for skills (local paths only)
        skills_dir: Legacy single directory option

    Returns:
        Async cleanup function that emits skill:unloaded events
    """
    config = config or {}
    logger.info(f"Mounting SkillsTool with config: {config}")

    # Declare observable events for hooks-logging auto-discovery
    obs_events = coordinator.get_capability("observability.events") or []
    obs_events.extend(
        [
            "skills:discovered",  # When skills are found during mount
            "skill:loaded",  # When skill loaded successfully (includes hooks config)
            "skill:unloaded",  # When skill is unloaded (for hook cleanup)
        ]
    )
    coordinator.register_capability("observability.events", obs_events)

    # Resolve skill sources (handles both local paths and git URLs)
    resolved_dirs = await _resolve_skill_sources(config, coordinator)

    tool = SkillsTool(config, coordinator, resolved_dirs)
    await coordinator.mount("tools", tool, name=tool.name)
    logger.info(
        f"Mounted SkillsTool with {len(tool.skills)} skills from {len(tool.skills_dirs)} sources"
    )

    # Mount skills visibility hook if enabled
    visibility_config = config.get("visibility", {})
    if visibility_config.get("enabled", True):  # Default: enabled
        from amplifier_module_tool_skills.hooks import SkillsVisibilityHook

        hook = SkillsVisibilityHook(tool.skills, visibility_config)

        # Register hook on provider:request event
        coordinator.hooks.register(
            event="provider:request",
            handler=hook.on_provider_request,
            priority=hook.priority,
            name="skills-visibility",
        )

        logger.info(f"Mounted skills visibility hook with {len(tool.skills)} skills")

    # Emit discovery event
    await coordinator.hooks.emit(
        "skills:discovered",
        {
            "skill_count": len(tool.skills),
            "skill_names": list(tool.skills.keys()),
            "sources": [str(d) for d in tool.skills_dirs],
        },
    )

    # Return cleanup function that emits skill:unloaded for each loaded skill
    async def cleanup() -> None:
        """Cleanup function that emits skill:unloaded events."""
        for skill_name in tool.loaded_skills:
            metadata = tool.skills.get(skill_name)
            if metadata:
                await coordinator.hooks.emit(
                    "skill:unloaded",
                    {
                        "skill_name": skill_name,
                        "source": metadata.source,
                        "hooks": metadata.hooks,
                    },
                )
                logger.debug(f"Emitted skill:unloaded for {skill_name}")
        tool.loaded_skills.clear()

    return cleanup


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

    def __init__(
        self,
        config: dict[str, Any],
        coordinator: "ModuleCoordinator | None" = None,
        resolved_dirs: list[Path] | None = None,
    ):
        """Initialize skills tool.

        Args:
            config: Tool configuration
            coordinator: Module coordinator for event emission (optional)
            resolved_dirs: Pre-resolved skill directories (from mount)
        """
        self.config = config
        self.coordinator = coordinator
        self.loaded_skills: set[str] = set()  # Track which skills have been loaded

        # Use pre-resolved dirs if provided, otherwise discover from config or defaults
        if resolved_dirs is not None:
            self.skills_dirs = resolved_dirs
            self.skills = discover_skills_multi_source(resolved_dirs)
            logger.info(
                f"Discovered {len(self.skills)} skills from {len(resolved_dirs)} sources"
            )
        else:
            # Fallback for direct instantiation (testing, etc.)
            # First check for cached skills from capability registry
            if coordinator:
                cached_skills = coordinator.get_capability("skills.registry")
                cached_dirs = coordinator.get_capability("skills.directories")
                if cached_skills is not None and cached_dirs is not None:
                    self.skills = cached_skills
                    self.skills_dirs = cached_dirs
                    logger.info(
                        f"Reusing {len(self.skills)} skills from capability registry"
                    )
                    return

            # Check config for skills directories
            dirs_from_config = self._get_dirs_from_config()
            if dirs_from_config:
                self.skills_dirs = dirs_from_config
                self.skills = discover_skills_multi_source(dirs_from_config)
                logger.info(
                    f"Discovered {len(self.skills)} skills from config directories"
                )
            else:
                self.skills_dirs = get_default_skills_dirs()
                self.skills = discover_skills_multi_source(self.skills_dirs)
                logger.info(
                    f"Discovered {len(self.skills)} skills from default directories"
                )

    def _get_dirs_from_config(self) -> list[Path] | None:
        """Extract skills directories from config for direct instantiation.

        Returns:
            List of paths if found in config, None otherwise.
        """
        # Check 'skills_dirs' config
        if "skills_dirs" in self.config:
            dirs = self.config["skills_dirs"]
            if isinstance(dirs, str):
                dirs = [dirs]
            return [Path(d).expanduser().resolve() for d in dirs]

        # Check 'skills_dir' config (legacy single directory)
        if "skills_dir" in self.config:
            return [Path(self.config["skills_dir"]).expanduser().resolve()]

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
                "list": {
                    "type": "boolean",
                    "description": "If true, return list of all available skills",
                },
                "search": {
                    "type": "string",
                    "description": "Search term to filter skills by name or description",
                },
                "info": {
                    "type": "string",
                    "description": "Get metadata for a specific skill without loading full content",
                },
                "source": {
                    "type": "string",
                    "description": "Register a new skill source. Accepts @namespace:path, git+https:// URLs, or local paths.",
                },
            },
        }

    async def _resolve_source(self, source: str) -> Path | None:
        """Resolve a source string to a local directory path.

        Handles @namespace:path (via mention_resolver), git+https:// URLs
        (via sources.py), and local filesystem paths.

        Args:
            source: Source string to resolve.

        Returns:
            Resolved local Path, or None if resolution fails.
        """
        # @namespace:path — use mention resolver
        if source.startswith("@"):
            if self.coordinator:
                resolver = self.coordinator.get_capability("mention_resolver")
                if resolver:
                    return resolver.resolve(source)
            return None

        # git+https:// or https:// — use existing sources.py
        if is_remote_source(source):
            return await resolve_skill_source(source)

        # Local path
        path = Path(source).expanduser().resolve()
        return path if path.exists() else None

    async def execute(self, input: dict[str, Any]) -> ToolResult:
        """
        Execute skill tool operation.

        Args:
            input: Tool parameters

        Returns:
            Tool result with skill content or list
        """
        # Source registration — resolve, discover, merge
        source_str = input.get("source")
        source_summary = None
        if source_str:
            resolved_path = await self._resolve_source(source_str)
            if resolved_path is None:
                return ToolResult(
                    success=False,
                    output=f"Could not resolve source: {source_str}",
                )

            new_skills = discover_skills(resolved_path)

            # Merge with first-match-wins: existing skills take priority
            added = []
            for name, metadata in new_skills.items():
                if name not in self.skills:
                    self.skills[name] = metadata
                    added.append(name)

            source_summary = (
                f"Source '{source_str}' resolved to {resolved_path}. "
                f"Found {len(new_skills)} skill(s), {len(added)} new: {', '.join(sorted(added)) if added else 'none (all duplicates)'}."
            )

            # Emit discovery event
            if self.coordinator:
                await self.coordinator.hooks.emit(
                    "skills:discovered",
                    {
                        "skill_count": len(new_skills),
                        "skill_names": list(new_skills.keys()),
                        "sources": [str(resolved_path)],
                    },
                )

            # If no other params, return the summary
            has_other_params = any(
                input.get(k) for k in ("skill_name", "list", "search", "info")
            )
            if not has_other_params:
                return ToolResult(success=True, output=source_summary)

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
                success=False,
                error={
                    "message": "Must provide skill_name, list=true, search='term', or info='name'"
                },
            )

        return await self._load_skill(skill_name)

    def _list_skills(self) -> ToolResult:
        """List all available skills."""
        if not self.skills:
            sources = ", ".join(str(d) for d in self.skills_dirs)
            return ToolResult(
                success=True, output={"message": f"No skills found in {sources}"}
            )

        skills_list = []
        for name, metadata in sorted(self.skills.items()):
            skills_list.append({"name": name, "description": metadata.description})

        lines = ["Available Skills:", ""]
        for skill in skills_list:
            lines.append(f"**{skill['name']}**: {skill['description']}")

        return ToolResult(
            success=True, output={"message": "\n".join(lines), "skills": skills_list}
        )

    def _search_skills(self, search_term: str) -> ToolResult:
        """Search skills by name or description."""
        matches = {}
        for name, metadata in self.skills.items():
            if (
                search_term.lower() in name.lower()
                or search_term.lower() in metadata.description.lower()
            ):
                matches[name] = metadata

        if not matches:
            return ToolResult(
                success=True, output={"message": f"No skills matching '{search_term}'"}
            )

        lines = [f"Skills matching '{search_term}':", ""]
        results = []
        for name, metadata in sorted(matches.items()):
            lines.append(f"**{name}**: {metadata.description}")
            results.append({"name": name, "description": metadata.description})

        return ToolResult(
            success=True, output={"message": "\n".join(lines), "matches": results}
        )

    def _get_skill_info(self, skill_name: str) -> ToolResult:
        """Get metadata for a skill without loading full content."""
        if skill_name not in self.skills:
            available = ", ".join(sorted(self.skills.keys()))
            return ToolResult(
                success=False,
                error={
                    "message": f"Skill '{skill_name}' not found. Available: {available}"
                },
            )

        metadata = self.skills[skill_name]
        info = {
            "name": metadata.name,
            "description": metadata.description,
            "version": metadata.version,
            "license": metadata.license,
            "compatibility": metadata.compatibility,
            "allowed_tools": metadata.allowed_tools,
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
                success=False,
                error={
                    "message": f"Skill '{skill_name}' not found. Available: {available}"
                },
            )

        metadata = self.skills[skill_name]
        body = extract_skill_body(metadata.path)

        if not body:
            return ToolResult(
                success=False,
                error={"message": f"Failed to load content from {metadata.path}"},
            )

        logger.info(f"Loaded skill: {skill_name}")
        self.loaded_skills.add(skill_name)  # Track for cleanup

        # Emit skill loaded event (hooks-shell module listens for this to activate skill-scoped hooks)
        if self.coordinator:
            await self.coordinator.hooks.emit(
                "skill:loaded",
                {
                    "skill_name": skill_name,
                    "source": metadata.source,
                    "content_length": len(body),
                    "version": metadata.version,
                    "skill_directory": str(metadata.path.parent),
                    "hooks": metadata.hooks,  # Claude Code-compatible hooks config (or None)
                },
            )

        return ToolResult(
            success=True,
            output={
                "content": f"# {skill_name}\n\n{body}",
                "skill_name": skill_name,
                "skill_directory": str(
                    metadata.path.parent
                ),  # Actual skill folder for companion files
                "loaded_from": metadata.source,  # Source directory for context
            },
        )
