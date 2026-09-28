# shuozhongwen · 说中文 ("Speak Chinese")

[中文](./README.md)

A Chinese-writing plugin for AI agents. It writes or revises a Chinese article with three goals at once: **keep the facts intact, lose the machine-translated "AI tone", and actually write well**.

Stripping AI tells alone tends to leave flat, lifeless prose. This plugin changes the order: identify the genre and decide what the piece has to say before writing; then hand the draft to a **fresh judge** that must back every score with a verbatim quote from the text (a score it cannot quote is void); revise from that evidence with a new judge each round, and stop as soon as the bar is met. The statistical "AI-likeness" score is a guardrail, never a target.

Works as a full Claude Code plugin (subagents and hooks included) and as an Agent Skill for Codex, Cursor, Gemini CLI and other agents. The judge can be any model behind an OpenAI-compatible API.

## How it works

Type `/shuozhongwen <topic or path to draft>`:

1. **Genre and standard**: practical text (reports, notices, plans) must be accurate and concise; argument must hold up; literary writing (essays, travel writing, fiction, reviews) must be good writing. The genre sets the pass bar.
2. **Thread, insight, fact ledger**: when revising someone else's draft, numbers, names, terms and causal directions are locked; missing details are never invented, only listed as "details to ask the author for".
3. **Write or revise** from meaning, not sentence by sentence.
4. **Editorial review and fact check** by two fresh subagents that see only the genre, the text and the rubric. Six dimensions: concrete detail, insight, language and imagery, rhythm, structure and tension, voice.
5. **Revise from evidence**: `review_zh.py` verifies each quote is verbatim and applies the bar. Weakest dimensions get fixed, a new judge re-reviews; at most three rounds.
6. **Hard gate**: `polish_check.py` checks invisible characters, four mechanical scans and the AI-likeness score.
7. **Deliver** the text with a short revision report.

Pass bar: literary genres average ≥ 4 with every dimension ≥ 3; practical and argument texts average ≥ 3.5 with every dimension ≥ 3; not flat; zero doubtful facts.

## Install

Python 3.10+. Core scripts use only the standard library.

### Claude Code

```bash
claude plugin marketplace add lan593674-byte/shuozhongwen
```

```bash
claude plugin install shuozhongwen@shuozhongwen
```

Then type `/shuozhongwen`. The judge and fact checker are the `shuozhongwen:judge` and `shuozhongwen:factcheck` subagents, running on the same model as your session.

### Codex, Cursor, Gemini CLI and other agents

```bash
git clone https://github.com/lan593674-byte/shuozhongwen.git
```

```bash
python shuozhongwen/install.py codex
```

Replace `codex` with `agents` (`~/.agents/skills`), `cursor`, `gemini`, or pass `--dest DIR`. The script copies the skill and points its paths back to your clone, so keep the clone where it is and re-run after `git pull`. `--uninstall` removes it.

Agents without subagents can use `judge_api.py` below, or ask you to paste the rubric and text into a brand-new chat. The skill forbids the writing session from grading itself.

### Any model as the judge

`scripts/judge_api.py` calls the judge through any OpenAI-compatible endpoint. Every call is a fresh, stateless request whose prompt comes from `agents/judge.md` and `agents/factcheck.md`, the same files the subagents use.

```bash
export SHUOZHONGWEN_API_BASE=https://api.deepseek.com/v1
export SHUOZHONGWEN_API_KEY=your-key
export SHUOZHONGWEN_MODEL=deepseek-chat
python scripts/judge_api.py draft.txt --genre 游记散文
```

OpenRouter, Kimi, Qwen, Volcengine Ark and local Ollama (`http://localhost:11434/v1`) all work. Using a different model than the writer reduces self-preference bias.

## Standalone tools

| Command | What it does |
|---|---|
| `python scripts/score_zh.py FILE --explain` | AI-likeness score with human-percentile and feature breakdown |
| `python scripts/haohao_scan.py FILE` | Mechanical scans: section numbering, meta-commentary, half-width punctuation, "not X but Y" |
| `python scripts/polish_check.py FILE` | Delivery gate: the above plus invisible characters |
| `python scripts/review_zh.py FILE --genre G --review review.json` | Verify a judge's JSON and apply the bar (no model call) |
| `python scripts/clean_text.py FILE -o OUT --stats` | Strip zero-width and other invisible characters |
| `python scripts/inspect_file.py FILE` | Report provenance metadata (C2PA, EXIF/XMP, Office properties, ...) |
| `python scripts/clean_file.py FILE -o OUT` | Strip it: PNG, JPEG, WebP, SVG, PDF, DOCX, XLSX, PPTX, EPUB, HTML, Markdown, MP4 and more |

## Claude Code hooks

- **After a file write** (PostToolUse): checks the file Claude just wrote for invisible characters and provenance metadata. Reports by default; set the plugin option `hook_mode` to `clean` to strip in place.
- **Before a reply is shown** (MessageDisplay): strips invisible characters; replies of 250+ characters get a one-line AI-likeness score. Display only; the transcript is untouched.

Environment: `SHUOZHONGWEN_SCORE=0` turns the score line off, `SHUOZHONGWEN_SCORE_MIN` sets the minimum length, `SHUOZHONGWEN_LOG_DIR` sets the log folder (counts and scores only, never reply text).

## About the AI-likeness score

A sign-constrained logistic regression over 19 Chinese stylometric features (sentence and paragraph length variation, connective density, ellipses and exclamations, pronoun and particle density, bigram repetition, stock-phrase markers, ...). Calibrated on 339 human texts (classics, pre-2020 Zhihu and Tieba long posts, free chapters of web novels, all hand-reviewed) and 101 texts from 8 models.

- Grouped cross-validation: with the `high` threshold at the human 95th percentile, 66% of AI passages are caught and 5% of human passages are misflagged.
- Leave-one-model-out: 47%–81% caught per unseen model.
- Held-out human text: 0% misflagged for colloquial forum posts, 4% for web fiction.

It only says whether the statistics resemble the AI texts in the calibration set. It is not a verdict of any commercial detector and not a detector-evasion tool; inside the workflow it is only a guardrail. The human calibration corpus is included in `calibration/human/` and `calibration/test/` **for personal study and research only, no commercial use**; copyright stays with the original authors and platforms and the MIT license does not cover it (see `calibration/corpus/README.md`).

## Credits and license

Adapted from two MIT-licensed projects: [haohao-shuohua](https://github.com/Job-Yang/jobyang-ai-skills) by Job-Yang and [watermarks-remover](https://github.com/guillaumemeyer/watermarks-remover) by Guillaume Meyer. See [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md).

Released under the [MIT License](./LICENSE).
