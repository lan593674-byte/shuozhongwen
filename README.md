# shuozhongwen · 说中文

[English](./README.en.md)

中文写作插件。写作 skill 以 [research-writing-skill](https://github.com/Norman-bury/research-writing-skill) 的写作内容重构，冲突以上游规范为准；保留 shuozhongwen 的独立评审打分、按证据改写、AI 相似度检查和数据保真流程。

支持 Claude Code，以及通过 `install.py` 安装的 Codex、Cursor、Gemini CLI。现有主命令保持三个：

| 命令 | 用途 |
|---|---|
| `/shuozhongwen` | 中文文章新写、材料写作、改稿和翻译 |
| `/shuozhongwen lunwen` / `/shuozhongwen:lunwen` | 论文规划、综述、章节写作、学术改稿和翻译 |
| `/shuozhongwen qingli` / `/shuozhongwen:qingli` | 沿用零宽字符、乱码清理及自动备份 |

`baozhen`、`xueshu` 仍是内部约束，不是新增主命令。

## 写作依据与范围

整合选题与结构规划、任务包和阶段门、文献检索与来源核实、证据驱动的引言和相关工作、逐章论证、文科社科/医学/法学规范、实验与统计结果的文字表述、中英翻译与润色、信息保留的去 AI 化、投稿前自审与返修、LaTeX 正文和引用。

不整合绘图、生图或环境安装。写作参考放在 `skills/shuozhongwen/references/research/`，按任务读取；没有新增 skill 命令。上游来源固定到 commit `6f7959554b4614d879d79cb4ece9ed04a7c8a88c`，许可见 `third_party/LICENSE.research-writing-skill`。

去 AI 化不等于压缩。保留研究对象、数据范围、样本口径、方法条件、指标含义、结论强度和局限，用中文自然语序与语义衔接形成连续段落。允许有用的主题句、必要承接、章节编号和客观研究主语，不用固定模板次数替代内容评审。原文已经自然就轻改，未要求缩写不删必要信息。

短段润色按实际范围完成；中型或整篇论文使用计划、任务包、章节职责和两阶段检查，引言/相关工作先建立证据映射，实验/结果先确定协议和表结构。已有连续写作授权不重复索要逐章批准。计划和材料缺口不混进正文，缺真实数据不能捏造实验。

## 保留的评审与改写流程

读材料并列保真清单 → 按任务写或改 → 独立评委打分和核查 → 验证 JSON 原文证据 → 按证据改写并重核保真 → 换新评委复审 → 运行格式、结构、不可见字符及 AI 相似度检查 → 交付正文和修改报告。

保留六项评分、1–5 分、原文证据验证和最多三轮改写。文学平均 ≥ 4，非文学及论文平均 ≥ 3.5，每项 ≥ 3；论文另保留原稿/改稿双证据严谨性审核，实际退步须为 0。实用文不因没有文采或个人态度判退，模板与结构次数只作为提示。论文研究问题另做自审报告，不偷偷改用户数据。

MCP 仍提供 `judge`、`compare`、`factcheck`、`lunwen_judge`、`rigor`、`judge_status`，保留 3.8.0 的配置、任务检查、短材料选项、双盲对比接口和流式重试能力；这些接口不增加主命令。评委每轮只看标准、当前任务要求和全文，没有上轮评分或改稿经过。独立评委不可用时明确报告，不能以作者自评代替。

## 数据保真

每轮逐项核对数值、单位、有效位、术语、引语、表格公式、引用归属、方法条件、因果和结论边界。原稿疑点列给作者，未经授权不更换数据。允许任务范围内的结构组织、引用格式统一与编号映射，不改变事实含义；授权检索产生的核实来源单列记录，不覆盖原稿。新增计算必须有任务授权、输入与算式记录，不能混成原始实验值。

交付包含修改对照、数据核对、独立评分、事实/严谨疑点、实际脚本结果和未完成项。模拟数据仅用于明确标记的规划稿，不能进入投稿终稿。

## qingli

`/shuozhongwen qingli 路径` 检测并清除文字、文件夹、Office/EPUB 文档中的零宽字符、控制字符及乱码。沿用原地清理前自动备份，保留空格、换行、编码、文档格式和元数据，逐项报告清理与无法恢复的内容。CLI：`python scripts/qingli.py 路径 [--check]`。清理功能和两个钩子不因写作重构改变。

## 安装

需要 Python 3.10 以上。核心脚本只用标准库，不用装依赖。

### Claude Code

```bash
claude plugin marketplace add lan593674-byte/shuozhongwen
```

```bash
claude plugin install shuozhongwen@shuozhongwen
```

也可以在 Claude Code 里用 `/plugin` 菜单添加。装好后输入 `/shuozhongwen` 使用，评委和事实核查是 `shuozhongwen:judge`、`shuozhongwen:factcheck` 两个子代理，跟当前会话用同一个模型。

### Codex、Cursor、Gemini CLI 等其他 agent

```bash
git clone https://github.com/lan593674-byte/shuozhongwen.git
```

```bash
python shuozhongwen/install.py codex
```

`codex` 可以换成 `agents`（`~/.agents/skills`）、`cursor`、`gemini`，或者用 `--dest 目录` 指定任意 skills 目录。脚本会把技能复制过去，并把里面的路径指回你 clone 的仓库，所以装完仓库别挪地方；`git pull` 之后重跑一次。卸载加 `--uninstall`。

没有子代理的 agent，评委有两种办法：用下面的 `judge_api.py` 调一个模型，或者让你在一个全新的对话里贴评分标准和正文。技能里写明了不允许在当前会话里自己给自己打分。

### 用别的模型当评委（推荐）

写稿的模型给自己打分会偏松：它认不出自己的套路，还会把这些套路当成好文章。所以插件优先让另一个模型当评委。

插件自带一个 MCP 服务（`scripts/judge_mcp.py`，Claude Code 装插件时自动启动），提供 `judge`、`compare`、`factcheck`、`lunwen_judge`、`rigor`、`judge_status` 六个工具。每次调用都是一次全新的请求，只带评分标准、当前任务要求和正文，返回结果已经按 `review_zh.py` 核对过。`/shuozhongwen` 流程里会先调用它，没配置时再退回到子代理。

接口、模型、密钥都放在一个配置文件里（默认 `~/.shuozhongwen/judge.json`，可以用环境变量 `SHUOZHONGWEN_JUDGE_CONFIG` 指到别处），以后换 API 只改这一处：

```bash
python scripts/judge_config.py set --base https://api.deepseek.com/v1 --model deepseek-chat --key-env DEEPSEEK_API_KEY
```

```bash
python scripts/judge_config.py test
```

- 密钥三种给法：`--key-env 环境变量名`（推荐）、`--key-file 路径:变量名`（从 .env 文件读）、`--key 明文`（不推荐）。密钥只在调用时读取，`show` 和 `judge_status` 都不显示它。
- 不同角色可以用不同模型：`--role factcheck=另一个模型`；`--clear-roles` 恢复全部用 `--model`。
- OpenRouter、Kimi、通义、火山方舟、本地 Ollama（`http://localhost:11434/v1`）都可以。

不在 Claude Code 里，也可以直接用命令行：`python scripts/judge_api.py 稿件.txt --genre 游记散文`；论文模式：`python scripts/judge_api.py 改稿.txt --genre 课程设计报告 --paper --original 原稿.docx`。

## 现有检查工具

| 命令 | 用途 |
|---|---|
| `python scripts/review_zh.py 稿件 --genre 文体 --review 审读.json` | 验证评分证据并应用评分门槛；论文用 `--paper --original 原稿 --rigor 严谨.json` |
| `python scripts/polish_check.py 稿件 [--paper]` | 不可见字符、格式、结构提示及 AI 相似度综合检查 |
| `python scripts/score_zh.py 稿件 --explain` | 校准 AI 相似度、tier、人类语料分位和特征说明 |
| `python scripts/structure_scan.py 稿件 [--paper]` | 上下文审读所需的结构信号 |
| `python scripts/haohao_scan.py 稿件 [--paper]` | 保留机械格式与表达扫描 |
| `python scripts/doc_text.py 稿件.docx -o 稿件.txt` | 读取正文及表格 |
| `python scripts/qingli.py 路径 [--check]` | 沿用清理流程 |
| `python scripts/inspect_file.py 文件` / `clean_file.py 文件 -o 输出` | 原有文件元数据工具，写作流程不自动调用 |

Windows 建议使用 `python -X utf8`。缺少 Python 时可保留稿件与人工核对，报告未运行的检查，不自动安装环境。

## Claude Code 里的两个钩子

装了插件后，这两个钩子一直生效，与 `/shuozhongwen` 无关。两个钩子都**只检查，不修改**任何文件或回复：

- **写文件后**（PostToolUse）：检查 Claude 刚写的文件里有没有零宽字符等不可见字符、乱码和来源元数据，结果记下来，不弹告警。
- **显示回复前**（MessageDisplay）：每条回复末尾都附一行检测报告：这条回复和这期间写入的文件有没有零宽字符、乱码，不论回复多短。250 字以上的回复在检测行上面再加一行 AI 相似度（字数太少时统计不可靠）。只改显示，不改会话记录。

例如：

```
---
AI 相似度 0.12（低，在人类文字的常见区间内）
检测：回复无零宽字符和乱码；写入的 2 个文件里 1 个有问题：notes.md：零宽/不可见字符 3｜清除可用 /shuozhongwen qingli
```

| 环境变量 | 作用 |
|---|---|
| `SHUOZHONGWEN_SCORE=0` | 关掉回复末尾的评分行 |
| `SHUOZHONGWEN_SCORE_MIN` | 评分的最短字数，默认 250 |
| `SHUOZHONGWEN_CHECK=0` | 关掉回复末尾的检测行 |
| `SHUOZHONGWEN_LOG_DIR` | 钩子日志目录，默认插件目录下的 `logs/`；只记计数和分数，不记回复原文 |

## AI 相似度的含义

`score_zh.py`、`zh_model.json` 及其校准词表保留。它根据中文文体统计估计与校准 AI 文本的相似度，不是商业检测器的 AI 率或查重率；短文不足以估计时明确报告，不能称为 0%。人类语料分位也不是“全文多少比例由 AI 生成”。

偏高时修真实的语言问题，保留信息，并重新评审；不为了最低分堆重复词、乱加标点或删结论边界。结构扫描信号交内容评审判断，不按次数否决正常论文结构。校准实验和局限见 `calibration/RESULTS.md`、`calibration/TEST_RESULTS.md`，旧评审校准结果不代表新标准已校准。

校准人类语料仅供个人学习、研究，不可商用，版权归作者和平台，不受本仓库 MIT 许可覆盖，见 `calibration/corpus/README.md`。

## 目录与许可

`skills/` 保留三个主命令和两个内部约束；`references/research/` 是按需写作参考。`agents/` 保留独立评委及审查员，`scripts/` 保留检测/清理工具，`hooks/` 保留只检查钩子。`install.py` 为其他 agent 安装入口，`tests/` 用 `python -m pytest -q` 验证。

整合的 MIT 项目包括 [research-writing-skill](https://github.com/Norman-bury/research-writing-skill)、[haohao-shuohua](https://github.com/Job-Yang/jobyang-ai-skills) 和 [watermarks-remover](https://github.com/guillaumemeyer/watermarks-remover)。版权和许可全文见 [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md) 与 `third_party/`。本项目以 [MIT 许可](./LICENSE) 发布。
