#!/usr/bin/env python3
"""Install the shuozhongwen skill for agents other than Claude Code.

Claude Code users install the plugin instead (see README). For other agents
this copies skills/shuozhongwen into the agent's skills folder and replaces
the placeholder ${CLAUDE_SKILL_DIR}/../.. with the absolute path of this
repository, so the skill can find scripts/ and agents/. Keep the repository
where it is after installing; re-run this script after `git pull`.

Usage:
  python install.py codex            # ~/.codex/skills/shuozhongwen
  python install.py agents           # ~/.agents/skills/shuozhongwen (shared skills folder)
  python install.py cursor           # ~/.cursor/skills/shuozhongwen
  python install.py gemini           # ~/.gemini/skills/shuozhongwen
  python install.py --dest DIR       # DIR/shuozhongwen
  add --uninstall to remove it again
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKILL = ROOT / "skills" / "shuozhongwen"
PLACEHOLDER = "${CLAUDE_SKILL_DIR}/../.."
PRESETS = {
    "codex": Path.home() / ".codex" / "skills",
    "agents": Path.home() / ".agents" / "skills",
    "cursor": Path.home() / ".cursor" / "skills",
    "gemini": Path.home() / ".gemini" / "skills",
}


def install(dest_root: Path) -> Path:
    target = dest_root / "shuozhongwen"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(SKILL, target)
    skill_md = target / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8")
    skill_md.write_text(text.replace(PLACEHOLDER, ROOT.as_posix()), encoding="utf-8")
    return target


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("agent", nargs="?", choices=sorted(PRESETS))
    p.add_argument("--dest", help="skills 目录（技能会装进 DEST/shuozhongwen）")
    p.add_argument("--uninstall", action="store_true")
    a = p.parse_args()
    if not a.agent and not a.dest:
        p.error("give an agent name or --dest")
    dest_root = Path(a.dest).expanduser() if a.dest else PRESETS[a.agent]
    if a.uninstall:
        target = dest_root / "shuozhongwen"
        if target.exists():
            shutil.rmtree(target)
        print(f"removed {target}")
        return 0
    target = install(dest_root)
    print(f"installed {target}")
    print(f"scripts: {ROOT / 'scripts'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
