# Skills System

You have access to the skills system for loading domain knowledge packages.

## What Are Skills?

Skills are domain knowledge packages following the [Anthropic Skills specification](https://agentskills.io/specification). They provide structured information through progressive disclosure:

- **Level 1 (Metadata)**: Name + description (~100 tokens) - always visible via list/search
- **Level 2 (Content)**: Full markdown body (~1-5k tokens) - loaded on demand
- **Level 3 (References)**: Additional files (0 tokens until accessed via read_file)

## Skills Visibility

When skills are available, you'll see them automatically in your context before each request:

```
<available_skills>
Available skills (use load_skill tool):

- **python-testing**: Best practices for Python testing with pytest
- **git-workflow**: Git branching and commit message standards
- **api-design**: RESTful API design patterns and conventions
</available_skills>
```

You don't need to call `load_skill(list=true)` first - skills are made visible automatically through the visibility hook.

## Available Tool: load_skill

**Operations:**

- `load_skill(list=true)` - List all available skills
- `load_skill(search="pattern")` - Filter by keyword
- `load_skill(info="skill-name")` - Get metadata only
- `load_skill(skill_name="skill-name")` - Load full content

**Usage Examples:**

```
# List available skills (if not already visible)
load_skill(list=true)

# Search for specific skills
load_skill(search="python")

# Load a skill
load_skill(skill_name="example-skill")
```

## Skills Discovery

Skills are discovered from these locations by default:
1. `.amplifier/skills/` (workspace)
2. `~/.amplifier/skills/` (user home)
3. `AMPLIFIER_SKILLS_DIR` environment variable

When multiple directories contain the same skill name, the first match wins (priority order matches the list order).

## Configuration

The skills tool supports custom directory configuration:

```yaml
tools:
  - module: tool-skills
    config:
      skills_dirs:
        - /custom/path/to/skills
        - /another/path
      visibility:
        enabled: true              # Show skills automatically (default: true)
        max_skills_visible: 50     # Limit for large collections (default: 50)
```
