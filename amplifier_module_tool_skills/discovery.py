"""
Skill discovery and metadata parsing.
Shared utilities for finding and parsing SKILL.md files.
"""

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Pattern for valid skill names per Anthropic Skills Spec
VALID_NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


@dataclass
class SkillMetadata:
    """Metadata from a SKILL.md file's YAML frontmatter."""

    name: str
    description: str
    path: Path
    source: str  # Which directory/source this came from
    version: str | None = None
    license: str | None = None
    allowed_tools: list[str] | None = None
    metadata: dict[str, Any] | None = None


def parse_skill_frontmatter(skill_path: Path) -> dict[str, Any] | None:
    """
    Parse YAML frontmatter from a SKILL.md file.

    Args:
        skill_path: Path to SKILL.md file

    Returns:
        Dictionary of frontmatter fields, or None if invalid
    """
    try:
        content = skill_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"Failed to read {skill_path}: {e}")
        return None

    # Check for YAML frontmatter (--- ... ---)
    if not content.startswith("---"):
        logger.debug(f"No frontmatter in {skill_path}")
        return None

    # Split on --- markers
    parts = content.split("---", 2)
    if len(parts) < 3:
        logger.debug(f"Incomplete frontmatter in {skill_path}")
        return None

    # Parse YAML
    try:
        frontmatter = yaml.safe_load(parts[1])
        return frontmatter if isinstance(frontmatter, dict) else None
    except yaml.YAMLError as e:
        logger.warning(f"Invalid YAML in {skill_path}: {e}")
        return None


def extract_skill_body(skill_path: Path) -> str | None:
    """
    Extract the markdown body from a SKILL.md file (without frontmatter).

    Args:
        skill_path: Path to SKILL.md file

    Returns:
        Markdown content after frontmatter, or None if invalid
    """
    try:
        content = skill_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"Failed to read {skill_path}: {e}")
        return None

    # Extract body after frontmatter
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()

    # No frontmatter, return entire content
    return content.strip()


def discover_skills(skills_dir: Path) -> dict[str, SkillMetadata]:
    """
    Discover all skills in a directory.

    Args:
        skills_dir: Directory containing skill subdirectories

    Returns:
        Dictionary mapping skill names to metadata
    """
    skills = {}

    if not skills_dir.exists():
        logger.debug(f"Skills directory does not exist: {skills_dir}")
        return skills

    if not skills_dir.is_dir():
        logger.warning(f"Skills path is not a directory: {skills_dir}")
        return skills

    # Scan for SKILL.md files (recursive)
    for skill_file in skills_dir.glob("**/SKILL.md"):
        try:
            # Parse frontmatter
            frontmatter = parse_skill_frontmatter(skill_file)
            if not frontmatter:
                logger.debug(f"Skipping {skill_file} - no valid frontmatter")
                continue

            # Extract required fields
            name = frontmatter.get("name")
            description = frontmatter.get("description")

            if not name or not description:
                logger.warning(f"Skipping {skill_file} - missing required fields (name, description)")
                continue

            # Validate name format (per Anthropic Skills Spec)
            if not VALID_NAME_PATTERN.match(name):
                logger.warning(
                    f"Skill '{name}' at {skill_file} has invalid name format. "
                    f"Names should be lowercase alphanumeric with hyphens (e.g., 'my-skill'). "
                    f"Continuing with discovery."
                )

            # Validate directory name matches skill name (per Anthropic Skills Spec)
            parent_dir_name = skill_file.parent.name
            if name != parent_dir_name:
                logger.warning(
                    f"Skill '{name}' at {skill_file} has mismatched directory name. "
                    f"Expected directory '{name}', but found '{parent_dir_name}'. "
                    f"Per Anthropic Skills Spec, the skill name should match the directory name. "
                    f"Continuing with discovery."
                )

            # Parse allowed-tools (note: YAML uses hyphen, Python uses underscore)
            allowed_tools = frontmatter.get("allowed-tools")

            # Create metadata
            metadata = SkillMetadata(
                name=name,
                description=description,
                path=skill_file,
                source=str(skills_dir),
                version=frontmatter.get("version"),
                license=frontmatter.get("license"),
                allowed_tools=allowed_tools,
                metadata=frontmatter.get("metadata"),
            )

            skills[name] = metadata
            logger.debug(f"Discovered skill: {name} at {skill_file}")

        except Exception as e:
            logger.warning(f"Error processing {skill_file}: {e}")
            continue

    logger.info(f"Discovered {len(skills)} skills in {skills_dir}")
    return skills


def discover_skills_multi_source(skills_dirs: list[Path] | list[str]) -> dict[str, SkillMetadata]:
    """
    Discover skills from multiple directories with priority.

    First-match-wins: If same skill name appears in multiple directories,
    the one from the earlier directory (higher priority) is used.

    Args:
        skills_dirs: List of directories to search, in priority order (highest first)

    Returns:
        Dictionary mapping skill names to metadata
    """
    all_skills: dict[str, SkillMetadata] = {}
    sources_checked = []

    for skills_dir in skills_dirs:
        dir_path = Path(skills_dir).expanduser().resolve()
        sources_checked.append(str(dir_path))

        if not dir_path.exists():
            logger.debug(f"Skills directory does not exist: {dir_path}")
            continue

        # Discover from this directory
        dir_skills = discover_skills(dir_path)

        # Merge with priority (first-match-wins)
        for name, metadata in dir_skills.items():
            if name not in all_skills:
                all_skills[name] = metadata
                logger.debug(f"Added skill '{name}' from {dir_path}")
            else:
                logger.debug(
                    f"Skipping duplicate skill '{name}' from {dir_path} (already have from {all_skills[name].source})"
                )

    logger.info(f"Discovered {len(all_skills)} skills from {len(sources_checked)} sources")
    return all_skills


def get_default_skills_dirs() -> list[Path]:
    """
    Get default skills directory search paths with priority.

    Priority order:
    1. AMPLIFIER_SKILLS_DIR environment variable
    2. .amplifier/skills/ (workspace)
    3. ~/.amplifier/skills/ (user)

    Returns:
        List of paths to check, in priority order
    """
    dirs = []

    # 1. Environment variable override (highest priority)
    if env_dir := os.getenv("AMPLIFIER_SKILLS_DIR"):
        dirs.append(Path(env_dir))

    # 2. Workspace directory
    dirs.append(Path(".amplifier/skills"))

    # 3. User directory
    dirs.append(Path("~/.amplifier/skills").expanduser())

    return dirs
