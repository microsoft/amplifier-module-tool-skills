"""Regression test: tool-skills must honor the runtime_skill_overlay capability.

Foundation's RuntimeOverlay (used by a mode's `contributes.skills`) registers a
`runtime_skill_overlay` capability listing skill sources contributed by the
currently-active modes. The skills tool must merge those into its live catalog so
`load_skill`/`list` see them while the mode is active, and drop them on revoke.
"""

from pathlib import Path

import pytest

from amplifier_module_tool_skills import SkillsTool


class _Hooks:
    async def emit(self, *_a, **_k):
        return None


class _Coordinator:
    def __init__(self):
        self.capabilities = {}
        self.hooks = _Hooks()
        self.config = {}

    def register_capability(self, name, value):
        self.capabilities[name] = value

    def get_capability(self, name):
        return self.capabilities.get(name)

    def get(self, name):
        return None


def _write_skill(root: Path, name: str, description: str) -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\nBody.\n",
        encoding="utf-8",
    )
    return skill_dir


@pytest.mark.asyncio
async def test_overlay_skill_is_loadable_only_while_contributed(tmp_path):
    # Base catalog is empty (no skills mounted at startup).
    base = tmp_path / "base"
    base.mkdir()
    overlay_skill = _write_skill(
        tmp_path / "overlay", "overlay-test-skill", "Contributed via the overlay."
    )

    coord = _Coordinator()
    tool = SkillsTool(config={}, coordinator=coord, resolved_dirs=[base])

    # 1. No mode active -> overlay empty -> skill absent.
    res = await tool.execute({"skill_name": "overlay-test-skill"})
    assert res.success is False
    assert "not found" in str(res.error).lower()

    # 2. Mode activates -> foundation registers the overlay -> skill resolves.
    coord.register_capability("runtime_skill_overlay", [str(overlay_skill)])
    res = await tool.execute({"list": True})
    assert "overlay-test-skill" in res.output["message"]

    res = await tool.execute({"skill_name": "overlay-test-skill"})
    assert res.success is True
    assert "overlay-test-skill" in res.output["content"]

    # 3. Mode deactivates -> overlay revoked -> skill dropped again.
    coord.register_capability("runtime_skill_overlay", [])
    res = await tool.execute({"skill_name": "overlay-test-skill"})
    assert res.success is False
    assert "not found" in str(res.error).lower()


@pytest.mark.asyncio
async def test_overlay_absent_is_a_noop(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    coord = _Coordinator()  # no runtime_skill_overlay capability registered
    tool = SkillsTool(config={}, coordinator=coord, resolved_dirs=[base])
    res = await tool.execute({"list": True})
    assert res.success is True
