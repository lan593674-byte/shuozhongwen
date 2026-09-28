# 人类校准语料

- `public-domain/`：25 篇现代经典（鲁迅、朱自清、萧红、许地山、胡适、徐志摩），作者去世都已超过 50 年，属于公有领域，文本取自维基文库，全文收录。
- `MANIFEST.csv`：全部 388 份人类样本的清单（编号、来源、原文链接、字数、用于训练还是留出测试）。知乎回答、贴吧帖子和起点免费章节仍受版权保护，这里只给链接，不收录正文。需要的话用 `calibration/fetch_zhihu.py`、`import_tieba.py` 等脚本自己抓取，再运行 `calibration/calibrate.py` 重新校准。

清单由 `calibration/build_manifest.py` 生成。
