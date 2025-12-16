# Amplifier Skills Tool Module

Tool for loading domain knowledge from skills in Amplifier.

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

Provides explicit skill discovery and loading capabilities for Amplifier agents. Skills are reusable knowledge packages that provide specialized expertise, workflows, and best practices following the [Anthropic Skills](https://github.com/anthropics/skills) format.

**Progressive disclosure knowledge packages**:
- **Level 1 (Metadata)**: Name + description (~100 tokens) - Always visible
- **Level 2 (Content)**: Full markdown body (~1-5k tokens) - Loaded on demand
- **Level 3 (References)**: Additional files (0 tokens until accessed)

## Contract

**Module Type:** Tool  
**Mount Point:** `tools`  
**Entry Point:** `amplifier_module_tool_skills:mount`

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
- **Load mode**: `{content, skill_name, skill_directory, loaded_from}` object

## Configuration

### Recommended: Global Configuration

Add to `~/.amplifier/settings.yaml` to make skills available to **all profiles**:

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

### Project-Specific Configuration

Add to `.amplifier/settings.local.yaml` for project-only skills:

```yaml
skills:
  dirs:
    - .amplifier/skills  # Project-specific skills (merged with global)
```

### Per-Profile Override

Override skills directories for a specific profile:

```yaml
tools:
  - module: tool-skills
    config:
      skills_dirs:  # Override - ignores settings.yaml for this profile
        - /special/skills/dir
```

### Bundle Configuration

Bundles work identically to profiles - same configuration format:

```yaml
bundle:
  name: my-bundle
  version: 1.0.0

tools:
  - module: tool-skills
    source: git+https://github.com/robotdad/amplifier-module-tool-skills@main
    config:
      skills_dirs:
        - ~/.amplifier/skills
        - ./project-skills
```

Run with: `amplifier run -B my-bundle "your prompt"`

**Note:** Bundles use the same configuration priority as profiles (config → settings.yaml → defaults).

### Configuration Priority

1. **Profile/Bundle config** (`skills_dirs` in tool config) - highest priority
2. **Settings.yaml** (`skills.dirs` in global/project settings) - recommended
3. **Defaults** (`.amplifier/skills`, `~/.amplifier/skills`, `$AMPLIFIER_SKILLS_DIR`) - fallback

## Usage Example

### In Python

```python
from amplifier_module_tool_skills import SkillsTool

# Create tool
tool = SkillsTool(config={}, coordinator=None)

# List all skills
result = await tool.execute({"list": True})
# Returns: {"message": "...", "skills": [{"name": "...", "description": "..."}]}

# Search for skills
result = await tool.execute({"search": "python"})
# Returns: {"message": "...", "matches": [{"name": "python-standards", ...}]}

# Get metadata
result = await tool.execute({"info": "python-standards"})
# Returns: {"name": "...", "description": "...", "version": "...", ...}

# Load skill content
result = await tool.execute({"skill_name": "python-standards"})
# Returns: {"content": "# python-standards\n\n...", "skill_directory": "/path/to/skill"}
```

### In Profile

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
```

### Agent Workflow

```
User: "Create a new tool module for database access"

Agent calls: load_skill(search="module")
Response: "**module-development**: Guide for creating modules..."

Agent calls: load_skill(skill_name="module-development")
Response: [Full guide with protocols, entry points, patterns]

Agent: Creates module following the skill's patterns
```

## Quick Start with Anthropic Skills

```bash
# 1. Clone Anthropic's skills repository
git clone https://github.com/anthropics/skills ~/anthropic-skills

# 2. Configure in settings.yaml
cat >> ~/.amplifier/settings.yaml << 'EOF'
sources:
  tool-skills: git+https://github.com/microsoft/amplifier-module-tool-skills@main

skills:
  dirs:
    - ~/anthropic-skills/skills
    - ~/.amplifier/skills
EOF

# 3. Add tool to your profile
# In profile frontmatter:
# tools:
#   - module: tool-skills

# 4. Use in any session
amplifier run "List available skills"
```

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

## SKILL.md Format

Skills use YAML frontmatter with markdown body:

```markdown
---
name: skill-name  # Required: unique identifier (lowercase with hyphens)
description: What this skill does and when to use it  # Required
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
**Format:** See [Anthropic Skills specification](https://github.com/anthropics/skills)

## Creating Skills

### Simple Skill

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

# Reference files (loaded on-demand by agent using read_file)
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
# Add to ~/.amplifier/settings.yaml
sources:
  tool-skills: file:///absolute/path/to/amplifier-module-tool-skills
```

**Option 2: Workspace Convention**

```bash
# In your development workspace
mkdir -p .amplifier/modules
ln -s /path/to/amplifier-module-tool-skills .amplifier/modules/tool-skills
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

> [!NOTE]
> This project is not currently accepting external contributions, but we're actively working toward opening this up. We value community input and look forward to collaborating in the future. For now, feel free to fork and experiment!

Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit [Contributor License Agreements](https://cla.opensource.microsoft.com).

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft
trademarks or logos is subject to and must follow
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.

## License

MIT
