"""Generate AI-side calibration samples from several models.

- Volcengine Ark (key read at runtime from env ARK_API_KEY, never stored):
  deepseek-v4.1-flash, kimi-k3, glm-5.3, doubao-seed-2.0-pro, minimax-m3
- Codex CLI (ChatGPT subscription), isolated with --ignore-user-config --ignore-rules
  --ephemeral so no skills/memories/AGENTS.md shape the output: gpt-6-luna, gpt-5.5

Each model gets 12 of the 24 prompts (rotating), so every genre is covered by
several models. Output: calibration/ai/<model>__<prompt>.txt; existing files are
skipped, so the script can be re-run to fill gaps.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

OUT = Path(__file__).resolve().parent / "ai"
ARK_BASE = "https://ark.cn-beijing.volces.com/api/plan/v3"
ARK_MODELS = ["deepseek-v4.1-flash", "kimi-k3", "glm-5.3", "doubao-seed-2.0-pro", "minimax-m3"]
CODEX_MODELS = ["gpt-6-luna", "gpt-5.5"]
CODEX = os.environ.get("CODEX_BIN", "codex")

TAIL = "直接输出正文，不要标题以外的任何说明。"
NATURAL = "写得自然一点，像真人随手写的，别有 AI 腔。"
PROMPTS = {
    "p01_essay_autumn": "写一篇 700 字左右的散文，写北方城市的秋天。",
    "p02_essay_grandma": "写一篇 700 字左右的回忆性散文，写外婆家的厨房。",
    "p03_comment_phone": "写一篇 700 字左右的时评，谈年轻人刷短视频停不下来这件事。",
    "p04_comment_exam": "写一篇 700 字左右的评论文章，谈高考志愿该听父母的还是听自己的。",
    "p05_speech_grad": "写一篇 600 字左右的大学毕业典礼学生代表发言稿。",
    "p06_speech_company": "写一篇 600 字左右的公司年会上部门负责人的致辞。",
    "p07_fiction_train": "写一篇 800 字左右的小说片段：春运火车上，两个陌生人聊起各自回家的原因。",
    "p08_fiction_shop": "写一篇 800 字左右的小说片段：县城一家要关门的旧书店的最后一天。",
    "p09_qa_sleep": "有人问：总是熬夜，怎么才能把作息调回来？请用 600 字左右回答。",
    "p10_qa_python": "有人问：零基础想学 Python 做数据分析，该怎么安排学习？请用 600 字左右回答。",
    "p11_work_weekly": "替一个后端工程师写一份本周工作周报，600 字左右，内容涉及接口性能优化和一次线上故障处理。",
    "p12_work_plan": "写一份 700 字左右的方案，说明公司内部知识库从飞书文档迁移到自建 Wiki 的计划。",
    "p13_wechat_money": "写一篇 800 字左右的公众号文章，主题是普通上班族怎么开始记账。",
    "p14_wechat_travel": "写一篇 800 字左右的公众号游记，写一次去大理的旅行。",
    "p15_review_book": "写一篇 700 字左右的书评，评《活着》。",
    "p16_review_film": "写一篇 700 字左右的影评，评电影《流浪地球》。",
    "p17_news_release": "写一篇 600 字左右的新闻稿：某市图书馆新馆开放，推出 24 小时自助借阅。",
    "p18_news_event": "写一篇 600 字左右的新闻报道：某高校学生团队在机器人比赛中获得全国一等奖。",
    "p19_student_essay": "以“那一次，我学会了坚持”为题写一篇 700 字左右的中学生作文。",
    "p20_student_letter": "写一封 600 字左右给十年后自己的信。",
    "p21_copy_coffee": "给一家社区精品咖啡馆写 500 字左右的品牌介绍文案。",
    "p22_copy_app": "给一款记单词 App 写 500 字左右的应用商店介绍文案。",
    "p23_social_rant": "写一篇 600 字左右的社交媒体长帖，吐槽租房遇到的奇葩房东。",
    "p24_social_share": "写一篇 600 字左右的社交媒体长帖，分享自己坚持跑步一年的变化。",
}
NATURAL_KEYS = {"p02_essay_grandma", "p08_fiction_shop", "p09_qa_sleep", "p13_wechat_money",
                "p14_wechat_travel", "p20_student_letter", "p23_social_rant", "p24_social_share"}


def ark_key() -> str:
    key = os.environ.get("ARK_API_KEY")
    if not key:
        raise SystemExit("No Ark API key: set ARK_API_KEY")
    return key


def prompt_text(key: str) -> str:
    return PROMPTS[key] + (NATURAL if key in NATURAL_KEYS else "") + TAIL


def ark(model: str, text: str, key: str) -> str:
    body = {"model": model, "messages": [{"role": "user", "content": text}], "max_tokens": 16000}
    req = urllib.request.Request(ARK_BASE + "/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                return json.load(r)["choices"][0]["message"].get("content") or ""
        except (urllib.error.URLError, TimeoutError):
            if attempt == 3:
                raise
            time.sleep(20 * (attempt + 1))
    return ""


def codex(model: str, text: str) -> str:
    with tempfile.TemporaryDirectory(dir=str(OUT.parent)) as work:
        out = Path(work) / "out.txt"
        subprocess.run([CODEX, "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
                        "--skip-git-repo-check", "-s", "read-only", "-m", model, "-C", work,
                        "-o", str(out), text], stdin=subprocess.DEVNULL, capture_output=True,
                       timeout=900, check=False)
        return out.read_text(encoding="utf-8") if out.exists() else ""


def jobs() -> list[tuple[str, str]]:
    keys = list(PROMPTS)
    out = []
    for i, model in enumerate(ARK_MODELS + CODEX_MODELS):
        chosen = keys[i % 2::2]  # alternate halves across models
        out += [(model, k) for k in chosen]
    return out


def run(job, key):
    model, pk = job
    path = OUT / f"{model}__{pk}.txt"
    if path.exists():
        return f"skip {path.name}"
    try:
        text = codex(model, prompt_text(pk)) if model in CODEX_MODELS else ark(model, prompt_text(pk), key)
    except Exception as e:
        return f"FAIL {model} {pk}: {type(e).__name__}"
    if len(text.strip()) < 200:
        return f"EMPTY {model} {pk}"
    path.write_text(text.strip() + "\n", encoding="utf-8")
    return f"OK   {path.name} {len(text)}"


def main() -> int:
    OUT.mkdir(exist_ok=True)
    key = ark_key()
    js = jobs()
    ark_jobs = [j for j in js if j[0] in ARK_MODELS]
    codex_jobs = [j for j in js if j[0] in CODEX_MODELS]
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(run, j, key) for j in ark_jobs]
        futs += [ex.submit(run, j, key) for j in codex_jobs[:0]]
        cx = ThreadPoolExecutor(max_workers=2)
        futs += [cx.submit(run, j, key) for j in codex_jobs]
        for f in futs:
            print(f.result(), flush=True)
        cx.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
