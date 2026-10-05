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

### Data fidelity (enforced when revising a draft or writing from your material)

Before revising a draft, or writing a new piece from material you provide, the plugin loads the `baozhen` constraint skill. When writing from material, not every figure has to be used, but whatever is used is copied exactly: no rounding, no conversions, no new numbers derived from it, and nothing filled in from the web. In both cases numbers, tables, citations and references, terms, hedges such as "possibly" or "mainly", causal direction and claims are never changed or invented, and when revising, never removed. A figure that looks wrong, even one the fact checker flags, only goes into the "for the author to check" list of the report.

### Clean invisible characters and garbled text: `/shuozhongwen qingli`

`/shuozhongwen qingli PATH` (or `/shuozhongwen:qingli`) finds and removes zero-width and other invisible characters and garbled text (U+FFFD, control characters, 锟斤拷/烫烫烫, and mojibake such as 涓枃 or Ã©, restored to the original characters when possible) in files, folders, Office/EPUB documents or pasted text. Spaces, line endings, encoding and document formatting are left alone; originals are backed up first. The report lists what was removed and where, and which spots lost characters the author must restore. CLI: `python scripts/qingli.py PATH [--check]`.

### Papers: `/shuozhongwen lunwen`

In Claude Code it is also a standalone command, `/shuozhongwen:lunwen`, listed in the plugin menu.

For academic papers, theses, course-project and lab reports: only the language changes, never the research. AI tells are removed while keeping formal academic register (no colloquialisms, no metaphors); numbering, tables, formulas, citations and references stay as they are. A dedicated academic language judge (`lunwen-judge`) scores accuracy, concision, register, coherence, consistency and template-free prose (average ≥ 3.5, each ≥ 3). The academic rigor review skill `xueshu`, active only in this mode, runs a fresh reviewer (`rigor`) over the original and the revision: any loss of rigor (data, hedges, causality, claims, terms, citations, register) must be zero, and problems in the original itself are listed for the author, not fixed. The report includes a sentence-by-sentence change table.

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

### Another model as the judge (recommended)

A model grading its own draft is too lenient: it does not see its own habits and tends to reward them. The plugin ships an MCP server (`scripts/judge_mcp.py`, started by Claude Code with the plugin) with the tools `judge`, `factcheck`, `lunwen_judge`, `rigor` and `judge_status`. Each call is a fresh request carrying only the rubric and the text, and the result is already checked by `review_zh.py`. The `/shuozhongwen` workflow uses it first and falls back to subagents when it is not configured.

Endpoint, model and key live in one config file (`~/.shuozhongwen/judge.json`, or wherever `SHUOZHONGWEN_JUDGE_CONFIG` points), so switching APIs means editing one place:

```bash
python scripts/judge_config.py set --base https://api.deepseek.com/v1 --model deepseek-chat --key-env DEEPSEEK_API_KEY
```

```bash
python scripts/judge_config.py test
```

Keys can come from an environment variable (`--key-env`), a .env file (`--key-file PATH:VAR`) or plain text (`--key`, not recommended); they are read at call time and never displayed. `--role factcheck=MODEL` sets a model per role. OpenRouter, Kimi, Qwen, Volcengine Ark and local Ollama all work. Outside Claude Code use the CLI: `python scripts/judge_api.py draft.txt --genre 游记散文`.

## Standalone tools

| Command | What it does |
|---|---|
| `python scripts/score_zh.py FILE --explain` | AI-likeness score with human-percentile and feature breakdown |
| `python scripts/haohao_scan.py FILE` | Mechanical scans: section numbering, meta-commentary, half-width punctuation, "not X but Y" |
| `python scripts/polish_check.py FILE` | Delivery gate: the above plus invisible characters; `--paper` skips the numbering scan, reference lists are exempt from the punctuation scan |
| `python scripts/doc_text.py FILE.docx -o FILE.txt` | Extract the text and tables of a .docx |
| `python scripts/review_zh.py FILE --genre G --review review.json` | Verify a judge's JSON and apply the bar (no model call) |
| `python scripts/clean_text.py FILE -o OUT --stats` | Strip zero-width and other invisible characters |
| `python scripts/inspect_file.py FILE` | Report provenance metadata (C2PA, EXIF/XMP, Office properties, ...) |
| `python scripts/clean_file.py FILE -o OUT` | Strip it: PNG, JPEG, WebP, SVG, PDF, DOCX, XLSX, PPTX, EPUB, HTML, Markdown, MP4 and more |

## Claude Code hooks

Both hooks only check; they never modify a file or a reply.

- **After a file write** (PostToolUse): checks the file Claude just wrote for invisible characters, garbled text and provenance metadata, and records the result (no pop-up).
- **Before a reply is shown** (MessageDisplay): every reply, however short, ends with a check line: invisible characters or garbled text in the reply and in files written meanwhile. Replies of 250+ characters also get an AI-likeness line above it (the statistics are unreliable on shorter text). Display only; the transcript is untouched.

Environment: `SHUOZHONGWEN_SCORE=0` turns the score line off, `SHUOZHONGWEN_SCORE_MIN` sets the minimum length, `SHUOZHONGWEN_CHECK=0` turns the check line off, `SHUOZHONGWEN_LOG_DIR` sets the log folder (counts and scores only, never reply text).

## About the AI-likeness score

A sign-constrained logistic regression over 19 Chinese stylometric features (sentence and paragraph length variation, connective density, ellipses and exclamations, pronoun and particle density, bigram repetition, stock-phrase markers, ...). Calibrated on 339 human texts (classics, pre-2020 Zhihu and Tieba long posts, free chapters of web novels, all hand-reviewed) and 101 texts from 8 models.

- Grouped cross-validation: with the `high` threshold at the human 95th percentile, 66% of AI passages are caught and 5% of human passages are misflagged.
- Leave-one-model-out: 47%–81% caught per unseen model.
- Held-out human text: 0% misflagged for colloquial forum posts, 4% for web fiction.

It only says whether the statistics resemble the AI texts in the calibration set. It is not a verdict of any commercial detector and not a detector-evasion tool; inside the workflow it is only a guardrail. The human calibration corpus is included in `calibration/human/` and `calibration/test/` **for personal study and research only, no commercial use**; copyright stays with the original authors and platforms and the MIT license does not cover it (see `calibration/corpus/README.md`).

## Credits and license

Adapted from two MIT-licensed projects: [haohao-shuohua](https://github.com/Job-Yang/jobyang-ai-skills) by Job-Yang and [watermarks-remover](https://github.com/guillaumemeyer/watermarks-remover) by Guillaume Meyer. See [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md).

Released under the [MIT License](./LICENSE).
