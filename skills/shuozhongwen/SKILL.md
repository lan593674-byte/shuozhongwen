---
name: shuozhongwen
description: 说中文：中文写作、改稿和翻译；以 research-writing-skill 的信息保留、证据驱动和自然行文规范为主，保留独立评审打分、按证据改写、AI 相似度检查与数据保真。只在用户输入 /shuozhongwen 时使用。
argument-hint: "[lunwen|qingli] 题目、写作要求或稿件路径"
disable-model-invocation: true
---

# 说中文

插件根目录 `R` = `${CLAUDE_SKILL_DIR}/../..`，脚本目录 `S` = `R/scripts`。其他 agent 用 `install.py` 安装时会写入实际根路径。Python 使用 `python3 -X utf8`，Windows 使用 `python -X utf8`，需要 3.10 以上。

写作规范以 [research-writing-skill](https://github.com/Norman-bury/research-writing-skill) 为主。用户当前要求优先；旧文学偏好、扫描阈值或评委建议与上游冲突时，以整合的 `references/research/` 为准。数据、证据和结论边界必须保留，不能为自然度或评分编造、删减、替换事实。内部参考不增加用户命令。

## 三个入口

- `/shuozhongwen`：中文文章的新写、材料写作、改稿、翻译，按下文执行。
- `/shuozhongwen lunwen` 或 `/shuozhongwen:lunwen`：论文规划、文献综述、章节写作、学术改稿与翻译，读 `references/lunwen.md`。识别到明确论文任务就进入论文流程，不为切换模式重复询问。
- `/shuozhongwen qingli` 或 `/shuozhongwen:qingli`：读 `R/skills/qingli/SKILL.md`，沿用现有清理、备份和检查流程。

`baozhen`、`xueshu` 仍是内部约束。写作不调用绘图、生图、音视频处理或环境安装等无关能力。

## 写作与改稿

### 1. 读上下文，确定交付

先读要求、原稿、材料和已有计划，确定读者、用途、文体、长度、语言、格式和修改范围。已有信息直接采用，只问影响实际写作的缺项。短段润色直接进入改稿，不机械要求七轮问答或整篇项目。长篇、多章或多轮任务按 `references/research/planning.md` 保存计划；已有连续写作授权时不重复索要逐章批准。

区分语言润色、结构重写、材料新写、题目新写、翻译和明确要求的扩缩写。未要求缩写，就不把去 AI 化当压缩。结构改动服务于任务，不以“只能逐句改”限制已授权的重写，也不把普通润色扩大为改变观点或增补研究。

### 2. 锁定保真与证据

有原稿或材料时先读 `R/skills/baozhen/SKILL.md`，记录数值与单位、术语、引语引用、表格公式、对象和方法条件、结论强度、因果方向、局限及出处。清单和资料缺口放工作记录，不混进正文。

材料新写可按主题取舍，但采用的事实必须可追溯。授权的文献检索或背景新写可增加核实来源，单独登记，不用新资料偷偷替换原稿数据。题目新写先查证事实，不编作者经历、文献、引语和实验结果。关键内容缺失就明确待补。

### 3. 按任务写，保留信息

必读 `references/research/core.md`；改稿、翻译、去 AI 化与扩缩写再读 `references/research/revision-translation.md`。用语义关系连接连续段落，明确主语、对象、方法、条件和判断边界。避开机械连接词、空壳强调、英文直译语序和空泛拔高；保留必要承接、解释与少量重复，不把每句削成同样的短句。

正文默认不用加粗、斜体和要点堆砌，段间空一行；计划、步骤、参数与用户要求的格式可以用列表。主题句、必要收束、章编号、引用和客观研究主语不是天然的 AI 腔。信息已完整自然时轻改即可。

实用文准确具体，评论凭依据论证。文学任务可按 `references/craft.md` 调节声音、细节与节奏，但不能强迫每篇有发现、第一人称或画面，更不能补造素材。论文按论文入口执行。

### 4. 独立打分与事实核对

保存全文。优先现有 MCP：`judge_status` 后并行调用 `judge`（`genre` + `path` 或 `text`；有明确任务时附 `task`）和 `factcheck`（全文；题目新写设 `own: true`）。不改评委配置或密钥。每轮都是全新请求，不提供上一轮分数、作者身份或改稿经过。

MCP 未配置或失败时，用两个全新的独立子代理，分别只给 `R/agents/judge.md` 或 `R/agents/factcheck.md` 的标准、文体、当前任务要求与全文。已有兼容接口也可运行 `python S/judge_api.py 稿件 --genre 文体`，有明确任务时加 `--task 任务要求`；素材不足时沿用 `--short-material`，不编造内容凑长度。都不可用时保留稿件并明确“未完成独立评审”，不能自己打分冒充。

保存原始 JSON 并运行：

```text
python S/review_zh.py 稿件 --genre 文体 --review 审读.json --facts 核查.json
```

题目新写加 `--own`。非文学平均 ≥ 3.5，文学平均 ≥ 4，每项 ≥ 3；证据必须来自全文。结构信号与模板数量用于定位，不机械按次数判退。原材料疑点列给作者，不擅改；新增说法必须经来源核实。

### 5. 按证据改写与复审

先修保真、证据和逻辑，再修最弱语言项。建议必须过保真清单；需要未知事实或改变研究结论的，列为待作者处理。改后重核清单、换新评委复审。过线就停，不为刷分再改；最多三轮，未过时保留稿件并说明卡点。

### 6. 检查与交付

```text
python S/polish_check.py 稿件
python S/score_zh.py 稿件 --explain
```

保留不可见字符、格式、结构和校准 AI 相似度检测。`polish_check.py` 通过要求为不可见字符 0、未保护的中文正文格式通过、AI 相似度不在 high；篇幅不足不能估计时单列“未评”，不算已通过 AI 检测。逐处审读提示，不能为清零删有效论证、引用和限定。偏高时按信息保留原则处理真实模板问题，改后复审，不追求最低分；真实问题已修但仍 high 时，交付注明“该检查未通过”，不继续损伤信息。结果是统计相似度及人类语料分位，不是某家检测器的 AI 率或查重率，不能把未评写成 0%。

没有 Python 可继续写作和人工保真核对，报告“未运行脚本检查”，不自动安装环境。未执行或失败项目不声称通过。

交付正文及简短报告：任务/文体与范围、主要改动、数据核对、独立评分与采纳意见、事实疑点/待补材料、实际检查和 AI 相似度含义、未完成项。长任务更新计划及能力使用审计。沿用用户项目路径，未指定时工作文件尽量放 D 盘，不覆盖原稿。

## 按需参考

- `references/lunwen.md`：论文流程与全部学术写作参考路由。
- `references/research/core.md`：共同写作规范。
- `references/research/planning.md`：范围对齐、任务包、阶段门和记录。
- `references/research/revision-translation.md`：翻译、信息保留改写及扩缩写。
- `references/craft.md`：文学任务补充方法。
- `R/skills/baozhen/SKILL.md`：保真清单。

现有钩子只检查，不修改回复或文件。清理使用 `qingli`。`symptom-dictionary.md`、`quick-scan-regex.md` 是检测兼容资源，不能覆盖本页写作规范。
