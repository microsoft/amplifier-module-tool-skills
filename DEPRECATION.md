# ⚠️ Deprecation Notice

This module has been **archived and consolidated** into [amplifier-bundle-skills](https://github.com/microsoft/amplifier-bundle-skills).

## What Changed

- **Module location:** Moved to `amplifier-bundle-skills/modules/tool-skills/`
- **Standalone repo:** No longer maintained as a standalone repository
- **Integration method:** Use the consolidated bundle instead

## Migration Path

### For existing users:

**Option 1: Use the consolidated bundle (Recommended)**

```yaml
includes:
  - bundle: git+https://github.com/microsoft/amplifier-bundle-skills@main
```

**Option 2: Use the behavior from the consolidated bundle**

```yaml
includes:
  - bundle: git+https://github.com/microsoft/amplifier-foundation@main
  - bundle: git+https://github.com/microsoft/amplifier-bundle-skills@main#subdirectory=modules/tool-skills/behaviors/skills.yaml
```

## Timeline

- **Last update:** March 2026
- **Status:** Read-only archive
- **Support:** Issues and PRs should be filed in [amplifier-bundle-skills](https://github.com/microsoft/amplifier-bundle-skills)

## Why This Change

Consolidating modules into a single bundle improves:
- 📦 **Dependency management** — Single source of truth for skills infrastructure
- 🔄 **Maintenance burden** — One place to update, test, and version
- 🤝 **Integration** — Easier to keep skills, skills-CLI, and related capabilities in sync

See [amplifier-bundle-skills](https://github.com/microsoft/amplifier-bundle-skills) for the current home of this module and related skills infrastructure.
