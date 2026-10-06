# 人类校准语料

> **声明：本目录及 `calibration/human/`、`calibration/test/` 中的语料不可用于任何商业用途，只能作为个人学习、研究使用。**
> 文字的版权归各原作者及平台所有，本仓库的 MIT 许可**不适用于**这些语料。
> 如果你是原作者或权利人，希望移除某篇内容，请在本仓库提 Issue，注明 `MANIFEST.csv` 里的编号，收到后会尽快删除。
>
> **Notice:** the texts in this folder, `calibration/human/` and `calibration/test/` are for personal study and research only; no commercial use. Copyright remains with the original authors and platforms; the MIT license of this repository does **not** cover them. Rights holders can open an issue to request removal.

- `calibration/human/`：训练用的 62 篇人类文字。其中 25 篇现代经典（鲁迅、朱自清、萧红、许地山、胡适、徐志摩）取自维基文库，已进入公有领域；其余是贴吧长帖和起点免费章节，都经过人工审核，营销、搬运类已剔除（记录见 `calibration/rejected.txt`）。
- `calibration/test/`：没有参与训练的留出测试文本，`spoken/` 是贴吧口语长帖，`webnovel/` 是 2024 年以前开始连载的起点网文免费章节。
- `MANIFEST.csv`：每一篇的文件路径、来源、原文链接、字数、用途（训练或测试），由 `calibration/build_manifest.py` 生成。

重新校准：`python calibration/calibrate.py`；留出测试：`python calibration/evaluate.py`。
