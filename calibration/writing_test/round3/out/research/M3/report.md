# 执行报告：外公的菜园（research-writing-skill / M3）

## 按技能走的步骤
1. 读入口 SKILL.md，按要求调用 skills/using-research-writing 路由；读 modules/workflow-lifecycle.md 和 plan-template/。
2. paper-orchestration：按它的定义，多段落成文算中型任务，所以先建 plan/ 和任务包（plan/task-packets/essay.md）。多代理分章门禁只管整篇论文，这里不适用。
3. brainstorming-research：用户不在线，七轮问答没法逐一问。答案都从用户请求和 material.md 里取：文体是回忆散文，题目《外公的菜园》，约 700 字，唯一来源是笔记，没有 LaTeX 模板，输出 Markdown/纯文本。我把用户的原始请求当作确认，写进 project-overview.md、outline.md（9 段，按时间顺序，每段标了对应的笔记条目）和 notes.md。
4. writing-chapters + writing-humanities + writing-core：正文写到 chapters/01-外公的菜园.md，初稿原样冻结为 draft1.txt。
5. 两阶段 Review + verification：
   - 阶段一（规范合规）：初稿 584 字（含标点），低于 630–770 区间，不通过。
   - 阶段二（质量/事实）：逐句对照笔记，找出 4 处笔记外内容，见下文。
   - 跑了 scripts/style_check.sh。它报出一处“最后”（字面义，不是过渡词），也改写掉了。
6. 更新 plan/progress.md，写了能力使用审计；更新了 stage-gates.md。

## 改了什么（draft1 → final）
- 删掉或替换笔记里没有的内容：“我待得最多的地方就是这块菜园”、“浇不了几垄”、“每次都交代一句”、“后来我不再去外公家过暑假了”。修改过程中自己新加的“问起来”“打满了”两处，也删了。
- 字数从 584 扩到 677（含标点）。扩写没有加任何新事实，只用了三种办法：
  - 年份换算：七个夏天、五年、又过了两年；
  - 回指前文已有的事实：塘水就是浇菜的水，大旱那年才去井里挑；清明看到的塘就是当年见底的那口；倒掉的是爬过丝瓜扁豆的那道篱笆；外公的菜园里也种过辣椒；
  - 把笔记的分句写完整。
- 没有加任何感官描写、心理活动、对话或议论。唯一的引语是笔记里原有的两句。

## 按用户指令偏离技能默认的地方
- 散文用第一人称“我”，不用“本文/本研究”客观表述，也不受“禁用我认为”这类论文规则约束（正文里本来也没有）。
- 不做文献检索、引用核验、LaTeX、图表。research_quality_gate.ps1 面向论文项目，没有运行。
- 用户确认环节（头脑风暴汇总确认、写完每章确认）都没法实时做，已在 notes.md 和本报告里记录。

## 结果
- final.txt：正文 677 字（含标点），去掉标点为 590 个汉字和数字；10 段；style_check 全部 OK。
