# Amplifier Skills Tool Module

Tool for loading domain knowledge from skills in Amplifier.

## What Are Skills?

Skills are **folders of instructions, scripts, and resources that agents load dynamically to improve performance on specialized tasks** (see [Anthropic Skills](https://github.com/anthropics/skills)).

This module brings Anthropic Skills support to Amplifier, enabling:
- Progressive disclosure of domain knowledge
- Reusable instruction packages for specialized tasks
- Integration with Anthropic's skills ecosystem

## Quick Start with Anthropic Skills

```bash
# 1. Clone Anthropic's skills repository (optional)
git clone https://github.com/anthropics/skills ~/anthropic-skills

# 2. Configure in settings.yaml (one-time setup)
cat >> ~/.amplifier/settings.yaml << 'EOF'
sources:
  tool-skills: git+https://github.com/microsoft/amplifier-module-tool-skills@main

skills:
  dirs:
    - ~/anthropic-skills/skills
    - ~/.amplifier/skills
EOF

# 3. Add tool to your profile
# In your profile's frontmatter:
# tools:
#   - module: tool-skills

# 4. Use in any session
amplifier run "List available skills"
```

All Anthropic skills are now available to your agent!

## Prerequisites

- **Python 3.11+**
- **[UV](https://github.com/astral-sh/uv)** - Fast Python package manager

### Installing UV

```bash
# macOS/Linux/WSL
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## Purpose

Provides explicit skill discovery and loading capabilities for Amplifier agents. Skills are reusable knowledge packages that provide specialized expertise, workflows, and best practices.

## Contract

**Module Type:** Tool  
**Mount Point:** `tools`  
**Entry Point:** `amplifier_module_tool_skills:mount`

## What Are Skills?

Skills are **progressive disclosure knowledge packages**:

- **Level 1 (Metadata)**: Name + description (~100 tokens) - Always visible
- **Level 2 (Content)**: Full markdown body (~1-5k tokens) - Loaded on demand
- **Level 3 (References)**: Additional files (0 tokens until accessed)

**Token Efficiency Example:**
```
Without Skills: 6000 tokens of guidelines always loaded
With Skills: 300 tokens metadata + 2000 tokens when needed
Savings: 60-65% token reduction
```

## Tools Provided

### `load_skill`

Load domain knowledge from an available skill.

**Operations:**

1. **List skills**: `load_skill(list=true)` - Show all available skills
2. **Search skills**: `load_skill(search="pattern")` - Filter by keyword
3. **Get metadata**: `load_skill(info="skill-name")` - Metadata only
4. **Load content**: `load_skill(skill_name="skill-name")` - Full content

**Input Schema:**

```json
{
  "type": "object",
  "properties": {
    "skill_name": {"type": "string"},
    "list": {"type": "boolean"},
    "search": {"type": "string"},
    "info": {"type": "string"}
  }
}
```

**Output:**

- **List mode**: Array of `{name, description}` objects
- **Search mode**: Filtered array of matching skills
- **Info mode**: Metadata object (name, description, version, license, path)
- **Load mode**: `{content, skill_name, loaded_from}` object

## Configuration

### Recommended: Global Configuration via Settings

Add to `~/.amplifier/settings.yaml` to make skills available to **all profiles automatically**:

```yaml
# Module source
sources:
  tool-skills: git+https://github.com/microsoft/amplifier-module-tool-skills@main

# Skills directories - applies to all profiles
skills:
  dirs:
    - ~/anthropic-skills/skills  # Optional: Anthropic's skills collection
    - ~/.amplifier/skills         # User-specific skills
```

Then add the tool to any profile:

```yaml
# In any profile
tools:
  - module: tool-skills  # No config needed - reads from settings.yaml
```

**That's it!** All profiles using tool-skills now have access to your configured skills directories.

### Project-Specific Configuration

Add to `.amplifier/settings.local.yaml` for project-only skills:

```yaml
# Project skills directories (merged with global)
skills:
  dirs:
    - .amplifier/skills  # Project-specific skills
```

### Per-Profile Override (Advanced)

Override skills directories for a specific profile:

```yaml
tools:
  - module: tool-skills
    config:
      skills_dirs:  # Override - ignores settings.yaml for this profile
        - /special/skills/dir
```

### Configuration Priority

The tool reads skills directories in this order:

1. **Profile config** (`skills_dirs` in profile tool config) - highest priority
2. **Settings.yaml** (`skills.dirs` in global/project settings) - **recommended**
3. **Defaults** (`.amplifier/skills` and `~/.amplifier/skills`) - fallback

### Default Directories

If not configured anywhere, the tool searches:
- `.amplifier/skills/` (workspace)
- `~/.amplifier/skills/` (user home)
- `$AMPLIFIER_SKILLS_DIR` (environment variable)

### Using Anthropic Skills

```bash
# Clone Anthropic's skills repository
git clone https://github.com/anthropics/skills ~/anthropic-skills

# Add to your settings
cat >> ~/.amplifier/settings.yaml << 'EOF'
skills:
  dirs:
    - ~/anthropic-skills/skills
    - ~/.amplifier/skills
EOF
```

All skills from both directories become available to the agent.

## Skills Directory Structure

Skills follow the [Anthropic Skills format](https://github.com/anthropics/skills):

```
skills-directory/
├── design-patterns/
│   ├── SKILL.md          # Required: name and description in YAML frontmatter
│   └── examples/
│       └── module-pattern.md
├── python-standards/
│   ├── SKILL.md
│   ├── async-patterns.md
│   └── type-hints.md
└── module-development/
    └── SKILL.md
```

Default location: `.amplifier/skills/` (can configure multiple directories)

## SKILL.md Format

Skills use the [Anthropic Skills format](https://github.com/anthropics/skills) - YAML frontmatter with markdown body:

```markdown
---
name: skill-name  # Required: unique identifier (lowercase with hyphens)
description: What this skill does and when to use it  # Required: complete explanation
version: 1.0.0
license: MIT
metadata:  # Optional
  category: development
  complexity: medium
---

# Skill Name

Instructions the agent follows when skill is loaded.

## Quick Start

[Minimal example to get started]

## Detailed Instructions

[Step-by-step guidance]

## Examples

[Concrete examples]
```

**Required fields:** `name` and `description` in YAML frontmatter
**Format:** See [Anthropic Skills specification](https://github.com/anthropics/skills) for complete details

## Usage Examples

### In Profile Definition

```markdown
---
profile:
  name: module-creator
  description: Creates new Amplifier modules

tools:
  - module: tool-filesystem
  - module: tool-bash
  - module: tool-skills
---

You are an Amplifier module creator.

Before creating modules:
1. Call load_skill(list=true) to see available guidelines
2. Load module-development skill for patterns
3. Follow the guidance from the skill

Skills are configured globally in ~/.amplifier/settings.yaml
```

### Agent Workflow

```
User: "Create a new tool module for database access"

Agent thinks: "I should check for module development guidelines"

Agent calls: load_skill(search="module")
Response: "**module-development**: Guide for creating modules..."

Agent calls: load_skill(skill_name="module-development")
Response: [Full guide with protocols, entry points, patterns]

Agent uses: Creates module following the skill's patterns
```

### Progressive Loading Example

```python
# Small footprint initially - just metadata
result = await tool.execute({"list": True})
# Returns: ~300 tokens (list of 3 skills)

# Load only what's needed
result = await tool.execute({"skill_name": "python-standards"})
# Returns: ~2000 tokens (full skill content)

# Agent can then read references directly via filesystem
# .amplifier/skills/python-standards/async-patterns.md
# Only loaded if agent needs it
```

## Integration with context-skills (Optional)

**Advanced:** Use with `amplifier-module-context-skills` for automatic skills metadata injection.

The `context-skills` module wraps your context manager and automatically shows available skills in the system message without requiring the agent to call `load_skill(list=true)` first.

```yaml
# In profile with context-skills
session:
  context:
    module: context-skills
    config:
      base_context: context-simple
      auto_inject_metadata: true

tools:
  - module: tool-skills  # Reads from settings.yaml
```

**How they work together:**
1. Both modules read skills directories from `settings.yaml`
2. Context auto-injects skills list into system message
3. Tool provides `load_skill` for on-demand full content loading
4. Context tracks loaded skills (prevents redundant loading)

**When to use context-skills:**
- You want skills visible in system message automatically
- You don't want to spend the first tool call on listing skills

**When to use tool-skills alone (recommended):**
- Simpler setup (one module instead of two)
- Agent calls `load_skill(list=true)` first (one tool call)
- Most use cases don't need auto-injection

## Creating Skills

### Simple Skill Example

```bash
mkdir -p .amplifier/skills/my-skill
cat > .amplifier/skills/my-skill/SKILL.md << 'EOF'
---
name: my-skill
description: Does something useful. Use when you need X.
version: 1.0.0
license: MIT
---

# My Skill

## Purpose

[What this skill does]

## Usage

[How to use it]

## Examples

[Complete examples]
EOF
```

### Skill with References

```bash
mkdir -p .amplifier/skills/advanced-skill
cd .amplifier/skills/advanced-skill

# Main skill file
cat > SKILL.md << 'EOF'
---
name: advanced-skill
description: Advanced patterns
---

# Advanced Skill

## Quick Start

[Brief example]

## Detailed Guides

- See patterns.md for design patterns
- See examples.md for complete examples
EOF

# Reference files (loaded on-demand)
echo "# Patterns Guide" > patterns.md
echo "# Examples" > examples.md
```

## Testing

```bash
# Run all tests
uv run pytest

# Run specific test
uv run pytest tests/test_tool.py::test_list_skills -v

# Run with coverage
uv run pytest --cov
```

## Local Development

### For Module Developers

If you're developing the tool-skills module itself:

**Option 1: Source Override (Recommended)**

```bash
# Add local source override
amplifier source add tool-skills "file://$(pwd)"

# Or edit ~/.amplifier/settings.yaml manually:
# sources:
#   tool-skills: file:///absolute/path/to/amplifier-module-tool-skills
```

**Option 2: Workspace Convention**

```bash
# In your development workspace
mkdir -p .amplifier/modules
ln -s /path/to/amplifier-module-tool-skills .amplifier/modules/tool-skills

# Module automatically discovered
amplifier module show tool-skills
```

**Option 3: Environment Variable (Temporary)**

```bash
export AMPLIFIER_MODULE_TOOL_SKILLS=/path/to/amplifier-module-tool-skills
amplifier run "test"
```

### Testing Your Changes

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Format and check code
uv run ruff check .
uv run ruff format .

# Type checking
uv run pyright
```

## Dependencies

- `amplifier-core` - Core protocols and types
- `pyyaml>=6.0` - YAML parsing

## Contributing

See main Amplifier repository for contribution guidelines.

## License

MIT

