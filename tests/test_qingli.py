"""garble detection/repair and the qingli command."""

from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import garble

ROOT = Path(__file__).resolve().parents[1]
QINGLI = ROOT / "scripts" / "qingli.py"
ZW = chr(0x200B)


def moj(s: str) -> str:
    return s.encode("utf-8").decode("gbk", errors="ignore")


def test_detects_each_kind():
    t = f"零宽{ZW}字。丢字\ufffd。锟斤拷。响铃\x07。{moj('这份文件的编码搞错了')}。cafÃ©"
    c = garble.inspect(t)["counts"]
    assert c == {"invisible": 1, "replacement": 1, "control": 1, "placeholder": 1, "mojibake": 2}


def test_repair_restores_mojibake_and_removes_the_rest():
    t = f"开头{ZW}。{moj('这份文件的编码搞错了')}。café → cafÃ©。丢\ufffd字，锟斤拷。"
    out, rep = garble.repair(t)
    assert "这份文件的编码搞错了" in out and "cafe" not in out and "café → café" in out
    assert ZW not in out and "\ufffd" not in out and "锟斤拷" not in out
    assert rep["remaining"] == {} and rep["changed"]


def test_line_endings_and_spaces_are_kept():
    nbsp = chr(0xA0)
    crlf = chr(13) + chr(10)
    t = "第一行" + nbsp + "有不换行空格" + crlf + "第二行" + ZW + crlf
    out, _ = garble.repair(t)
    assert out == "第一行" + nbsp + "有不换行空格" + crlf + "第二行" + crlf


def test_genuine_text_is_not_flagged():
    files = glob.glob(str(ROOT / "calibration" / "human" / "*.txt"))[:200]
    samples = [Path(f).read_text(encoding="utf-8") for f in files] + [
        "鸿沟与涓涓细流，锦绣河山。", "Größe und Ärger, Ça va? Señor.", "谢谢夸奖，为什么呢？"]
    for s in samples:
        c = garble.inspect(s)["counts"]
        assert not c.get("mojibake") and not c.get("placeholder"), s[:40]


def test_report_shows_invisible_characters_by_code_point():
    item = garble.inspect("正文" + ZW + "有零宽")["items"][0]
    assert "⟨U+200B⟩" in item["context"] and item["line"] == 1


def run(*args, logs: Path):
    return subprocess.run([sys.executable, "-X", "utf8", str(QINGLI), *args], capture_output=True, text=True,
                          encoding="utf-8", env={**os.environ, "SHUOZHONGWEN_LOG_DIR": str(logs)})


def test_qingli_cleans_text_and_docx_in_place_with_backup(tmp_path):
    md = tmp_path / "a.md"
    md.write_bytes(f"---\r\nname: x\r\n---\r\n正文{ZW}。\r\n{moj('编码搞错了')}\r\n".encode("utf-8"))
    docx = tmp_path / "r.docx"
    with zipfile.ZipFile(docx, "w") as z:
        z.writestr("word/document.xml", f'<w:document xmlns:w="w"><w:t>报告{ZW}正文 &amp; 符号\ufffd</w:t></w:document>')
    logs = tmp_path / "logs"
    check = run(str(tmp_path), "--check", "--json", logs=logs)
    assert md.read_bytes().count(ZW.encode()) == 1  # --check changes nothing
    r = run(str(tmp_path), "--json", logs=logs)
    assert r.returncode == 0, r.stdout + r.stderr
    by = {Path(x["path"]).name: x for x in json.loads(r.stdout)}
    assert by["a.md"]["changed"] and by["a.md"]["mojibake_fixed"][0]["to"].startswith("编码搞错")
    # moj() dropped the bytes of the last character (errors="ignore"), as real
    # mojibake often has: that character is gone, the rest comes back
    assert md.read_bytes() == "---\r\nname: x\r\n---\r\n正文。\r\n编码搞错\r\n".encode("utf-8")
    xml = zipfile.ZipFile(docx).read("word/document.xml").decode("utf-8")
    assert xml == '<w:document xmlns:w="w"><w:t>报告正文 &amp; 符号</w:t></w:document>'
    assert Path(by["a.md"]["backup"]).read_bytes().count(ZW.encode()) == 1
    assert json.loads(check.stdout)[0]["changed"] is False


def test_qingli_text_mode_prints_report_and_cleaned_text(tmp_path):
    r = run("--text", "你好" + ZW + "世界", logs=tmp_path)
    assert "已清除：零宽/不可见字符 1" in r.stdout and r.stdout.rstrip().endswith("你好世界")


def test_qingli_skips_binary(tmp_path):
    (tmp_path / "x.bin").write_bytes(b"\x00\x01abc")
    r = run(str(tmp_path / "x.bin"), logs=tmp_path / "logs")
    assert "二进制文件" in r.stdout and r.returncode == 0
