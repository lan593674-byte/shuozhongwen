"""install.py: copies the skill and points it at this repository."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("install", ROOT / "install.py")
install = importlib.util.module_from_spec(spec)
spec.loader.exec_module(install)


def test_install_rewrites_placeholder(tmp_path):
    target = install.install(tmp_path)
    text = (target / "SKILL.md").read_text(encoding="utf-8")
    assert install.PLACEHOLDER not in text
    assert ROOT.as_posix() in text
    assert (target / "references" / "craft.md").exists()
    # the repo copy keeps the placeholder for Claude Code
    assert install.PLACEHOLDER in (ROOT / "skills" / "shuozhongwen" / "SKILL.md").read_text(encoding="utf-8")
