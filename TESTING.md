# Testing Skills Modules with Amplifier-Dev

This guide provides complete instructions for testing the skills modules in a clean amplifier-dev environment.

## Prerequisites

- **amplifier-dev** repository cloned and working
- **uv** installed for Python package management
- **Anthropic API key** configured

## Step 1: Install Skills Modules

```bash
cd amplifier-dev

# Install tool-skills module from GitHub
uv pip install git+https://github.com/robotdad/amplifier-module-tool-skills.git
```

Verify installation:
```bash
uv run amplifier module list | grep -i skill
```

Expected output:
```
│ tool-skills            │ tool         │ tools        │ Module: tool-skills     │
```

## Step 2: Create Test Skills

Create example skills directory:

```bash
mkdir -p .amplifier/skills/amplifier-philosophy
mkdir -p .amplifier/skills/python-standards
mkdir -p .amplifier/skills/module-development
```

**Create: `.amplifier/skills/amplifier-philosophy/SKILL.md`**

```markdown
---
name: amplifier-philosophy
description: Core design principles - mechanism vs policy, module architecture, kernel philosophy. Use when making architectural decisions.
version: 1.0.0
license: MIT
---

# Amplifier Philosophy: The Linux Kernel Metaphor

## Core Principle: Mechanism Not Policy

**If two teams might want different behavior, it belongs in a module, not the kernel.**

The kernel provides mechanisms (mount, emit, dispatch). Modules provide policies (what to mount, when to emit, how to handle).

## Key Patterns

- **Ruthless Simplicity**: Code you don't write has no bugs
- **Modules at Edges**: Kernel enables, doesn't choose
- **Event-Driven**: If it's important, emit an event
- **Fail-Safe**: Module failures never crash kernel

## Mount Point System

Think of modules as devices mounted at paths:
- `/mnt/providers/{name}` - LLM backends
- `/mnt/tools/{name}` - Agent capabilities
- `/mnt/context` - Conversation state
- `/mnt/orchestrator` - Execution loop
```

**Create: `.amplifier/skills/python-standards/SKILL.md`**

```markdown
---
name: python-standards
description: Python coding standards including type hints, async patterns, error handling. Use when writing Python code.
version: 1.0.0
license: MIT
---

# Python Coding Standards

## Type Hints

ALL functions must have complete type hints:

```python
from typing import Any

async def process_data(items: list[str], config: dict[str, Any]) -> dict[str, Any]:
    """Process data items with configuration."""
    results = {}
    for item in items:
        results[item] = await transform(item, config)
    return results
```

## Async Patterns

All I/O operations must be async:

```python
async def read_file(path: Path) -> str:
    content = path.read_text()
    return content
```

## Error Handling

Return errors, don't raise:

```python
from amplifier_core import ToolResult

async def execute(self, input: dict[str, Any]) -> ToolResult:
    try:
        result = await self._process(input)
        return ToolResult(success=True, output=result)
    except ValueError as e:
        return ToolResult(success=False, error={"message": str(e)})
```
```

**Create: `.amplifier/skills/module-development/SKILL.md`**

```markdown
---
name: module-development
description: Guide for creating Amplifier modules - protocols, entry points, mount functions. Use when creating new modules.
version: 1.0.0
license: MIT
---

# Module Development Guide

## Creating a New Module

### Step 1: Choose Protocol

- **Tool**: Agent capability (filesystem, bash, web)
- **Provider**: LLM backend (Anthropic, OpenAI)
- **Context**: Conversation state (simple, persistent)
- **Orchestrator**: Execution strategy (basic, streaming)

### Step 2: Implement Protocol

```python
from amplifier_core import ModuleCoordinator, ToolResult

class MyTool:
    name = "my-tool"
    description = "Does something useful"

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "param": {"type": "string", "description": "Parameter"}
            },
            "required": ["param"]
        }

    async def execute(self, input: dict[str, Any]) -> ToolResult:
        param = input.get("param")
        if not param:
            return ToolResult(success=False, error={"message": "param required"})

        result = f"Processed: {param}"
        return ToolResult(success=True, output={"result": result})
```

### Step 3: Create Mount Function

```python
async def mount(coordinator: ModuleCoordinator, config: dict[str, Any] | None = None) -> None:
    config = config or {}
    tool = MyTool(config)
    await coordinator.mount("tools", tool, name=tool.name)
    return
```
```

## Step 3: Create Test Profile

**Create: `.amplifier/profiles/test-skills.md`**

```markdown
---
profile:
  name: test-skills
  version: "1.0.0"
  description: "Test profile for skills modules"
  extends: dev

session:
  orchestrator:
    module: loop-basic
    config:
      max_turns: 10
      extended_thinking: false
  context:
    module: context-simple

tools:
  - module: tool-skills
    config:
      skills_dirs:
        - .amplifier/skills
---

# Skills Testing Agent

You are testing Amplifier's skills system.

## Available Skills

Skills are automatically discovered from `.amplifier/skills/`. You have access to:

- `load_skill(list=true)` - List all available skills
- `load_skill(search="term")` - Search skills by keyword
- `load_skill(info="name")` - Get metadata without full content
- `load_skill(skill_name="name")` - Load full skill content

## Testing Instructions

When asked to test skills:
1. List available skills
2. Load ONE skill of your choice
3. Summarize what that skill contains
4. Demonstrate progressive disclosure (metadata → content)
```

## Step 4: Verify Setup

Check profile is valid:

```bash
uv run amplifier profile show test-skills
```

Expected output should show:
- Session orchestrator: loop-basic
- Session context: context-simple
- Tools including: tool-skills
- Inheritance: foundation → base → dev → test-skills

## Step 5: Run Tests

### Interactive Mode

```bash
uv run amplifier run -P test-skills --mode chat
```

### Test Scenarios

**Test 1: Discovery**
```
"List all available skills"
```
Expected: Should list 3 skills with descriptions

**Test 2: Search**
```
"Search for skills related to 'python'"
```
Expected: Should find python-standards skill

**Test 3: Metadata Only**
```
"Get info about python-standards without loading it"
```
Expected: Returns name, description, version only (~100 tokens)

**Test 4: Progressive Loading**
```
"First list skills, then load the amplifier-philosophy skill"
```
Expected: Shows metadata first, then full content (~2-3k tokens)

**Test 5: Content Usage**
```
"Load the module-development skill and tell me the three key steps"
```
Expected: Loads full skill and summarizes the three steps

**Test 6: Skills Awareness**
```
"What skills do you have available? Don't load them, just tell me what you see"
```
Expected: Agent mentions skills from system instruction (auto-injected)

**Test 7: All Operations**
```
"List skills, search for 'module', get info on module-development, then load python-standards"
```
Expected: Demonstrates all four tool operations in sequence

### Single Prompt Mode

Quick functionality test:
```bash
uv run amplifier run -P test-skills "List available skills, then load python-standards and tell me one thing about type hints"
```

## Expected Behavior

### Progressive Disclosure

1. **Session Start**: Metadata auto-injected (~100 tokens for all skills)
2. **List Operation**: Returns skill names + descriptions
3. **Load Operation**: Returns full markdown content (~1-5k tokens per skill)
4. **Token Efficiency**: 60-65% savings vs always-loaded documentation

### Tool Operations

- `list=true`: Returns array of `{name, description}` objects
- `search="term"`: Filters skills by keyword
- `info="name"`: Returns metadata object without content
- `skill_name="name"`: Returns full skill markdown content

### Context Integration

- Skills metadata visible in system instruction automatically
- Agent can reference skills by name before loading
- Context tracks which skills have been loaded
- Prevents redundant loading

## Verification Checklist

After testing, verify:

- [ ] Both modules appear in `amplifier module list`
- [ ] Profile loads without errors
- [ ] Skills directory contains 3 example skills
- [ ] Agent can list all 3 skills
- [ ] Agent can search and find specific skills
- [ ] Agent can load full skill content
- [ ] Skills metadata appears in system instruction
- [ ] Progressive disclosure works (metadata → content)
- [ ] No "unknown tool" errors (minor display issue is known/expected)

## Cleanup

After testing, remove temporary files:

```bash
cd amplifier-dev

# Remove test artifacts (not committed to repo)
rm -rf .amplifier/skills/
rm .amplifier/profiles/test-skills.md
rm amplifier.log.jsonl

# Uninstall module (optional)
uv pip uninstall amplifier-module-tool-skills
```

The modules remain in their git repos and can be reinstalled anytime.

## Troubleshooting

### Modules Not Found

```bash
# Verify installation
uv run python -c "from amplifier_module_tool_skills import SkillsTool; print('✓ tool-skills')"
```

### Skills Directory Not Found

```bash
# Check path
ls -la .amplifier/skills/
# Should show 3 subdirectories with SKILL.md files
```

### Profile Invalid

```bash
# Validate profile structure
uv run amplifier profile show test-skills
# Should show inheritance chain and effective config
```

### Tool Appears as "unknown"

This is a known cosmetic issue in the logging/display layer. The tool functions correctly - verify by checking that you receive skill content. The display shows "unknown" but functionality is unaffected.

## Architecture Notes

### How It Works

1. **Discovery**: `tool-skills` scans configured directories on initialization
2. **List Skills**: Agent calls `load_skill(list=true)` to see available skills (~100 tokens)
3. **Explicit Loading**: Agent calls `load_skill(skill_name="...")` to load full content
4. **Tracking**: Context marks skills as loaded to prevent redundancy

### Token Economics

```
Without Skills:
- 6000 tokens: All documentation always loaded

With Skills:
- 100 tokens: Metadata for all skills (auto-injected)
- 2000 tokens: One skill loaded on-demand
- 0 tokens: Reference files (accessed via filesystem)
= 2100 tokens total (65% savings)
```

### Module Architecture

Both modules follow amplifier-dev kernel philosophy:
- Zero kernel changes
- Standard entry point pattern (`pyproject.toml`)
- Protocol-based (no inheritance)
- Event-observable (can emit lifecycle events)
- Fail-safe (errors don't crash kernel)

## Further Information

- **Module Repo**:
  - https://github.com/robotdad/amplifier-module-tool-skills
- **Documentation**: See README.md in each module repo
- **Example Skills**: See `tests/fixtures/skills/` in module repos
- **Skill Format**: YAML frontmatter + Markdown body

## Success Criteria

Testing is successful when:
1. ✅ Agent can discover all skills automatically
2. ✅ Agent can list, search, and load skills
3. ✅ Progressive disclosure saves 60-65% tokens
4. ✅ Skills content is useful and well-formatted
5. ✅ Integration works seamlessly (context + tool)
6. ✅ No crashes or errors during operation
