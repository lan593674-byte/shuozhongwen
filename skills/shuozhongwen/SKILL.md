---
name: shuozhongwen
description: 说中文：写或改一篇中文文章，要求去掉 AI 味、写出文学水准、事实经得起核查；/shuozhongwen lunwen 是论文特化，只改语言、保证学术严谨；/shuozhongwen qingli 清除零宽字符和乱码。只在用户输入 /shuozhongwen 时使用。
argument-hint: "[lunwen|qingli] 题目或稿件路径（可附文体，如“游记散文”“周报”；论文用 lunwen）"
disable-model-invocation: true
---

# 说中文

用户输入 `/shuozhongwen`，后面跟题目或稿件，就按下面的流程写或改一篇中文文章。目标三件事同时做到：**事实不动、没有 AI 腔、写得好**。只做减法去 AI 味，得到的是白开水；这套流程先定写什么，再写，再请全新的评委挑毛病，按证据改到过线为止。

插件根目录 `R` = `${CLAUDE_SKILL_DIR}/../..`（Claude Code 会自动换成实际路径；其他 agent 用 `install.py` 安装时会写成绝对路径），脚本在 `R/scripts`（下称 `S`）。Python 用 `python3 -X utf8`（Windows 上是 `python -X utf8`），需要 3.10 以上，核心脚本只用标准库。规则细则都在 `references/`，用到哪篇读哪篇，不用一次全读。

## 先看参数

- 第一个参数是 `lunwen`（如 `/shuozhongwen lunwen 报告.docx`，也可以用单独的命令 `/shuozhongwen:lunwen 报告.docx`）：论文特化。读 `references/lunwen.md`，按那里的流程走，**下面的流程不用**。学术论文、毕业论文、课程设计报告、实验报告、综述，用户没写 `lunwen` 你也认出来了，先问一句要不要改用论文模式。
- 第一个参数是 `qingli`（如 `/shuozhongwen qingli 报告.docx`，也可以用单独的命令 `/shuozhongwen:qingli`）：检测并清除零宽字符等不可见字符和乱码。读 `R/skills/qingli/SKILL.md`，按那里的步骤做，**下面的流程不用**。
- 其他情况：按下面的流程走。

**改的是别人给的稿子**（不是你从头写），动笔前先加载数据保真约束 `baozhen`：Claude Code 里调用技能 `shuozhongwen:baozhen`，其他 agent 读 `R/skills/baozhen/SKILL.md`。它全程生效，优先于本页的一切目标：原稿的数字、表格、引用、术语、论断强度一个都不改，看起来错了也只列给作者。

**没有 Python**（`python`、`python3`、`py` 都跑不起来）：告诉用户下面的检查脚本需要 Python 3.10 以上，请用户自己装或同意你来装（Windows：`winget install Python.Python.3.12`；macOS：`brew install python`）。用户不装，就跳过脚本那几步，在修改报告里写明“未跑脚本检查”，证据核对改为你逐条手工核对。不要自己把脚本改写成别的语言来代替。

## 流程

**1. 认文体，定标准**

- 实用文本（周报、通知、方案、说明、答复、技术文档）：准确、简洁、具体。读 `references/rules.md`。
- 议论文字（评论、知乎式回答、观点文章）：观点立得住、论证具体、有人在说话。读 `references/rules.md`，外加 `references/craft.md` 的「发现」「声音」。
- 文学性文字（散文、游记、随笔、小说、演讲、书评影评）：写得好。读 `references/craft.md`，再读 `references/rules.md` 的保真、去 AI 味和标题部分。

拿不准就问：读者读完要知道一件事（实用），同意一个看法（议论），还是看见、感到一些东西（文学）。文体要写具体，比如“城市随笔散文”，后面审读按它定标准。

**2. 定主线和“发现”，锁事实**

动笔前回答两个问题：这篇最值得写的、只属于它的“发现”是什么？用哪根主线把材料串起来？答不上来，先别写句子。

- 改别人的稿子：按 `baozhen` 先列数据清单，这些一个字都不动。原文没有的细节、经历、引语、数字、判断一律不补，缺了就列进“建议作者补充的细节”。原稿的数据你觉得不对，也不改，列进“待作者核对”。
- 自己从头写：可以用查得到的真实细节，写之前心里核对一遍，拿不准的不写。没去过的地方，不编“我”的亲身经历。

**3. 写或改**

从含义出发整篇写，别逐句翻译。文学性文字按 craft.md 的五根柱子：具体、发现、语言、节奏与结构、声音。删掉的套话和修饰，要换成具体细节，不能只删不补。开头直接进入，结尾落在一个画面或一句克制的话上，不总结、不号召。

**4. 编辑审读和事实核查（全新子代理）**

把稿子写进文件，然后在同一条消息里并行调用两个子代理。它们都是当前会话模型的全新实例，不带这次会话的任何上下文、CLAUDE.md 和技能，只看到你给的内容：

- 评委：子代理类型 `shuozhongwen:judge`，提示只写两样东西，不加任何说明、背景、改稿经过或作者信息：

  ```
  文体：城市随笔散文

  正文：
  <<<
  （完整正文）
  >>>
  ```

- 事实核查：子代理类型 `shuozhongwen:factcheck`，提示只写 `正文：` 加完整正文，**必须是全文**，不许只摘你想查的句子。实用文本里没有可核查的事实时，可以跳过这一步。

不在 Claude Code 里（没有 `shuozhongwen:judge` 这类子代理）时，任选一种，要求不变：评委每次都是全新的，只看到评分标准、文体和正文。

- 你的 agent 能开子代理（Codex、Cursor 等）：开一个全新的子代理，把 `R/agents/judge.md` 分隔线以下的内容当评分标准，后面接上面那段“文体 + 正文”；事实核查同理，用 `R/agents/factcheck.md`。不给子代理任何别的上下文。
- 用任意兼容 OpenAI 接口的模型当评委（也可以特意换一个和写作者不同的模型，减少自我偏好）：`python S/judge_api.py 稿件 --genre 城市随笔散文`，模型和接口用环境变量 `SHUOZHONGWEN_MODEL`、`SHUOZHONGWEN_API_BASE`、`SHUOZHONGWEN_API_KEY` 设。它把 JSON 存在稿件旁边，并直接给出下面 `review_zh.py` 的核对结果。
- 两样都没有：请用户在一个全新的对话里贴评分标准和正文，把返回的 JSON 交给你。不要在当前会话里自己给自己打分冒充审读。

把两个子代理返回的 JSON 原样存成文件，然后跑：

```
python S/review_zh.py 稿件 --genre 城市随笔散文 --review 审读.json --facts 核查.json
```

自己从头写的稿子加 `--own`。脚本逐项核对评委给的证据是不是原文原句，引不出原文的那一项作废，只要有作废项，这轮审读无效，换一个全新的评委重审。通过条件：文学性文字平均 ≥ 4、每项 ≥ 3；实用和议论文字平均 ≥ 3.5、每项 ≥ 3；不是白开水。事实存疑：自己写的稿子要改到 0；别人的稿子不算未通过，存疑项全部列进“待作者核对”，正文不动。

事实核查子代理会记错，它给的“正确数字”不能直接用：自己写的稿子，改之前要找到可靠来源；找不到就删掉那句或改成不含具体数字的说法。

**5. 按证据改，改完换新评委重审**

没过，就按脚本列出的最弱两项和评委的改法改。事实存疑的：自己写的稿子，找到来源后改正，找不到就删；别人的稿子，一律不改，列给作者。改完回到第 4 步，**每一轮都用全新的子代理**，不要把上一轮的评语、分数或“这是修改稿”告诉新评委。过了就停，不为刷分再改。改三轮还过不了，停下来，把卡住的项目和原因告诉用户。

评委的改法要过保真这一关：让你“补一个细节”“补一个发现”“加一句判断”，改别人的稿子时不能编，也不能自己加结论、评价、“这说明……”“意味着……”，只能列进“建议作者补充的细节”。评委的判断也会错（比如把本来成立的数学关系说成矛盾），照改之前先核对。

**6. 过硬闸**

```
python S/polish_check.py 稿件
```

要求不可见字符为 0、四条机械扫描（章节编号、元话语、半角标点、“不是 X 而是 Y”）都过、AI 相似度不在 high。AI 相似度只是护栏：落在人类常见区间就够了，**不往下压**。落在 high 时，按列出的项目用“写得更好”的办法改（补细节、删套话、调节奏），改完回第 4 步复审，确认质量没掉。

**7. 交稿**

给正文，再附一份简短的修改报告（模板见 `references/workflow.md`）：文体、主线、数据核对（改别人的稿子时，按 `baozhen`）、编辑审读的分数和照改的意见、事实核查结果、待作者核对、建议作者补充的细节、硬闸结果。AI 相似度只说明统计信号，不等于能通过哪家检测器。

## 参考文件

- `references/lunwen.md`：论文特化 `/shuozhongwen lunwen` 的完整流程
- `R/skills/baozhen/SKILL.md`：数据保真约束（改别人的稿子时必加载）
- `R/skills/xueshu/SKILL.md`：学术严谨性审查（只在论文模式用）
- `references/craft.md`：文学性文字怎么写好（具体、发现、语言、节奏结构、声音），以及怎么避免改成白开水
- `references/rules.md`：完整规则，包括保真、去 AI 味、比喻和各条红线、交付硬闸、标题、出稿前自检
- `references/workflow.md`：事实账本、三遍回读、修改报告模板
- `references/symptom-dictionary.md`、`before-after-worktext.md`、`rhythm-check.md`、`word-coining-checklist.md`、`protected-spans.md`、`chinese-four-principles.md`：症状库和各项细则
- `references/quick-scan-regex.md`：机械扫描的正则和命令

## 单项工具

- 只跑机械扫描：`python S/haohao_scan.py 稿件`
- 只看 AI 相似度：`python S/score_zh.py 稿件 --explain`
- 清不可见字符：`python S/clean_text.py 稿件 -o 输出 --stats --no-normalize-spaces`

## 文件清理

先检查，再另存输出，除非用户要求原地修改：

- 检查：`python S/inspect_file.py 文件`（加 `--json` 出结构化结果）
- 清理：`python S/clean_file.py 文件 -o 输出`，支持 PNG、JPEG、WebP、SVG、PDF、DOCX、XLSX、PPTX、ODT、EPUB、HTML、Markdown、LaTeX、MP4 等
- 整个目录体检：`python S/audit_dir.py 目录 --check-stylometry`
- 图片专用：`clean_image.py`；音频重编码：`clean_audio.py`（需要 ffmpeg）
- 视频和图片的像素级去水印（`--remove-pixel`）需要另装 CtrlRegen 或 MarkDiffusion 模型，默认不带

Claude Code 里有两个钩子，不受 `/shuozhongwen` 控制，一直生效，都**只检查、不修改**：写文件后的钩子检查刚写入的文件有没有零宽字符、乱码和来源元数据，把结果记下来；回复显示前的钩子在 250 字以上的回复末尾附一行 AI 相似度，紧接着一行“检测”：这条回复和这期间写入的文件有没有零宽字符、乱码（短回复只在写了文件或发现问题时才附）。要清除，用 `/shuozhongwen qingli`。其他 agent 没有这两个钩子，需要时手动跑 `python S/qingli.py 路径 --check`。
