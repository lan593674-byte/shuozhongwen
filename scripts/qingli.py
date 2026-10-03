#!/usr/bin/env python3
"""/shuozhongwen qingli: find and remove invisible characters and garbled text.

Targets: text files (.txt .md .py .json .csv ... anything that is not binary),
Office and EPUB documents (.docx .pptx .xlsx .odt .odp .ods .epub), whole
directories, or a piece of text (--text, or stdin with "-").

What it removes or repairs (see garble.py): zero-width and other invisible
format characters, U+FFFD replacement characters, C0 control characters,
锟斤拷/烫烫烫 placeholders, and UTF-8 text that was decoded with the wrong code
page (涓枃 → 中文, Ã© → é). Nothing else changes: spaces, line endings, file
encoding, formatting and metadata stay as they are. In documents only the text
inside XML text nodes is touched.

Files are cleaned in place. Before a file changes, the original is copied to a
backup folder (default <log dir>/qingli-backup/<time>/); --no-backup skips it.
--check only reports.

Usage:
  qingli.py 文件或目录 [更多路径] [--check] [--no-backup] [--json]
  qingli.py --text "要清理的文字"
  qingli.py -            (从标准输入读文字，清理后的文字写到标准输出)
Exit code: 0 = nothing left to fix, 1 = something remains (e.g. not repairable).
"""

from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import file_check  # noqa: E402
import garble  # noqa: E402
import hook_state  # noqa: E402

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".pytest_cache", "qingli-backup"}
MAX_BYTES = 50 * 1024 * 1024


def _repair_xml(xml: str) -> tuple[str, dict]:
    """Repair the text nodes of one XML part; markup is left alone."""
    total: dict = {"removed": {}, "mojibake_fixed": [], "items": []}

    def fix(m):
        raw = m.group(1)
        text = html.unescape(raw)
        new, rep = garble.repair(text)
        if not rep["changed"]:
            return m.group(0)
        for k, v in rep["removed"].items():
            total["removed"][k] = total["removed"].get(k, 0) + v
        total["mojibake_fixed"] += rep["mojibake_fixed"]
        total["items"] += rep["items"]
        return ">" + html.escape(new, quote=False) + "<"

    return file_check.XML_TEXT.sub(fix, xml), total


def clean_document(path: Path, dest: Path) -> dict:
    merged: dict = {"removed": {}, "mojibake_fixed": [], "items": []}
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(dest, "w") as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if file_check.ZIP_TEXT_PARTS.search(info.filename):
                xml = data.decode("utf-8", errors="surrogateescape")
                new, rep = _repair_xml(xml)
                if new != xml:
                    data = new.encode("utf-8", errors="surrogateescape")
                    for k, v in rep["removed"].items():
                        merged["removed"][k] = merged["removed"].get(k, 0) + v
                    merged["mojibake_fixed"] += rep["mojibake_fixed"]
                    merged["items"] += [dict(i, part=info.filename) for i in rep["items"]]
            zout.writestr(info, data)  # keeps each entry's name, order and compression
    return merged


def backup_root() -> Path:
    return hook_state.log_dir() / "qingli-backup" / datetime.now().strftime("%Y%m%d-%H%M%S")


def clean_file(path: Path, check: bool, backup: Path | None) -> dict:
    before = file_check.check_path(path)
    result = {"path": str(path), "kind": before["kind"], "found": before["counts"], "items": before["items"],
              "provenance": before["provenance"], "changed": False, "removed": {}, "mojibake_fixed": [],
              "remaining": {}, "backup": "", "skipped": before["skipped"]}
    if before["kind"] == "binary":
        result["skipped"] = "二进制文件，不是文字，跳过（图片、PDF、音视频的元数据用 clean_file.py）"
        return result
    if before["skipped"] or not before["counts"] or check:
        result["remaining"] = before["counts"]
        return result

    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        if before["kind"] == "document":
            rep = clean_document(path, tmp)
        else:
            raw = path.read_bytes()
            text = raw.decode("utf-8", errors="surrogateescape")
            new, rep = garble.repair(text)
            tmp.write_bytes(new.encode("utf-8", errors="surrogateescape"))
        if tmp.read_bytes() != path.read_bytes():
            if backup is not None:
                target = backup / path.name
                n = 1
                while target.exists():
                    target = backup / f"{path.stem}.{n}{path.suffix}"
                    n += 1
                backup.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
                result["backup"] = str(target)
            shutil.copymode(path, tmp)
            os.replace(tmp, path)
            result["changed"] = True
        result["removed"] = rep["removed"]
        result["mojibake_fixed"] = rep["mojibake_fixed"]
    finally:
        tmp.unlink(missing_ok=True)
    result["remaining"] = file_check.check_path(path)["counts"]
    return result


def iter_files(paths: list[Path]):
    for p in paths:
        if p.is_dir():
            for root, dirs, files in os.walk(p):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                for name in sorted(files):
                    f = Path(root) / name
                    if f.stat().st_size <= MAX_BYTES:
                        yield f
        elif p.is_file():
            yield p
        else:
            yield p  # reported as missing


def _where(item: dict) -> str:
    loc = f"第 {item['line']} 行" if item.get("line") else ""
    if item.get("part"):
        loc = f"{item['part']} {loc}".strip()
    ctx = item.get("context", "")
    return f"{loc}「{ctx}」" if ctx else loc


def report_file(r: dict, check: bool) -> list[str]:
    out = [f"■ {r['path']}"]
    if r["skipped"]:
        out.append(f"  {r['skipped']}")
        return out
    if not r["found"]:
        out.append("  没有零宽字符和乱码")
    elif check:
        out.append(f"  发现：{garble.summary(r['found'])}（只检查，未修改）")
    elif r["changed"]:
        out.append(f"  已清除：{garble.summary(r['removed'])}")
    for fx in r["mojibake_fixed"]:
        note = "，原文有字节已丢失，修复后仍可能缺字" if fx.get("lossy") else ""
        out.append(f"    乱码修复 第 {fx['line']} 行：「{fx['from'][:30]}」→「{fx['to'][:30]}」{note}")
    shown = 0
    for it in r["items"]:
        if it["type"] == "mojibake" or shown >= 12:
            continue
        label = garble.LABELS.get(it["type"], it["type"])
        what = it.get("label") or it.get("char") or it.get("text", "")
        if it.get("more"):
            out.append(f"    {label} {what} 另有 {it['more']} 处")
        else:
            lost = "（这里原来的字已丢失，需作者补）" if it["type"] in ("replacement", "placeholder") else ""
            out.append(f"    {label} {what} {_where(it)}{lost}".rstrip())
        shown += 1
    if r["provenance"]:
        out.append(f"  另有来源元数据：{'、'.join(r['provenance'])}（qingli 不处理，用 clean_file.py）")
    if r["remaining"] and not check:
        out.append(f"  仍未解决：{garble.summary(r['remaining'])}")
    if r["backup"]:
        out.append(f"  原文件备份：{r['backup']}")
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("paths", nargs="*", help="文件或目录；'-' 表示从标准输入读文字")
    p.add_argument("--text", help="直接给一段文字")
    p.add_argument("--check", action="store_true", help="只检查，不修改")
    p.add_argument("--no-backup", action="store_true", help="不备份原文件")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    if a.text is not None or a.paths == ["-"]:
        text = a.text if a.text is not None else sys.stdin.read()
        new, rep = garble.repair(text)
        found = garble.inspect(text)["counts"]
        if a.json:
            print(json.dumps({"text": new, "found": found, **{k: rep[k] for k in ("removed", "mojibake_fixed", "remaining")}},
                             ensure_ascii=False, indent=1))
        else:
            r = {"path": "（输入的文字）", "found": found, "items": rep["items"], "provenance": [], "changed": rep["changed"],
                 "removed": rep["removed"], "mojibake_fixed": rep["mojibake_fixed"], "remaining": rep["remaining"],
                 "backup": "", "skipped": ""}
            print("\n".join(report_file(r, a.check)))
            if not a.check:
                print("\n清理后的文字：\n" + new)
        return 1 if rep["remaining"] else 0

    if not a.paths:
        p.error("give files, directories, --text or '-'")
    backup = None if a.no_backup or a.check else backup_root()
    results = []
    for f in iter_files([Path(x).expanduser() for x in a.paths]):
        if not f.exists():
            results.append({"path": str(f), "skipped": "找不到这个文件", "found": {}, "items": [], "provenance": [],
                            "changed": False, "removed": {}, "mojibake_fixed": [], "remaining": {}, "backup": ""})
            continue
        results.append(clean_file(f, a.check, backup))
    if a.json:
        print(json.dumps(results, ensure_ascii=False, indent=1))
    else:
        dirty = [r for r in results if r["found"] or r["skipped"] or r["provenance"]]
        clean_count = len(results) - len(dirty)
        for r in dirty:
            print("\n".join(report_file(r, a.check)))
        changed = sum(1 for r in results if r["changed"])
        verb = "需要清理" if a.check else "已清理"
        print(f"\n共检查 {len(results)} 个文件：{verb} {changed if not a.check else len([r for r in results if r['found']])} 个，"
              f"{clean_count} 个没有问题。" + (f"原文件备份在 {backup}" if changed and backup else ""))
    return 1 if any(r["remaining"] for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
