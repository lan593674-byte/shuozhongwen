"""Equations and note citations must stay visible to fidelity reviewers."""

import xml.etree.ElementTree as ET
import zipfile

from doc_text import read_any

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def test_word_fraction_and_note_sources_remain_visible(tmp_path):
    doc = tmp_path / "source.docx"
    body = f'''<w:document xmlns:w="{W}" xmlns:m="{M}"><w:body>
    <w:p><w:r><w:t>阈值为：</w:t></w:r><m:oMath><m:f>
    <m:num><m:r><m:t>1</m:t></m:r></m:num><m:den><m:r><m:t>2</m:t></m:r></m:den>
    </m:f></m:oMath></w:p><w:p><w:r><w:t>法律论断</w:t>
    <w:footnoteReference w:id="2"/><w:endnoteReference w:id="3"/>
    </w:r></w:p></w:body></w:document>'''
    foot = f'''<w:footnotes xmlns:w="{W}">
    <w:footnote w:id="0" w:type="separator"><w:p><w:r><w:t>分隔符</w:t></w:r></w:p></w:footnote>
    <w:footnote w:id="2"><w:p><w:r><w:t>张某：《法学著作》，2020 年，第 12 页。</w:t></w:r></w:p></w:footnote>
    </w:footnotes>'''
    end = f'''<w:endnotes xmlns:w="{W}"><w:endnote w:id="3">
    <w:p><w:r><w:t>案例来源：案号 2023-9。</w:t></w:r></w:p></w:endnote></w:endnotes>'''
    with zipfile.ZipFile(doc, "w") as archive:
        archive.writestr("word/document.xml", body)
        archive.writestr("word/footnotes.xml", foot)
        archive.writestr("word/endnotes.xml", end)
    text = read_any(doc)
    assert "[脚注 2]" in text and "[尾注 3]" in text
    assert "张某：《法学著作》，2020 年，第 12 页。" in text
    assert "案例来源：案号 2023-9。" in text and "分隔符" not in text
    math = ET.fromstring(text.split("```xml\n", 1)[1].split("\n```", 1)[0])
    assert math.find(f".//{{{M}}}num/{{{M}}}r/{{{M}}}t").text == "1"
    assert math.find(f".//{{{M}}}den/{{{M}}}r/{{{M}}}t").text == "2"
    assert "阈值为：12" not in text


def test_word_namespace_aliases_table_attributes_and_entities(tmp_path):
    doc = tmp_path / "table.docx"
    body = f'''<a:document xmlns:a="{W}"><a:body><a:tbl a:rsidR="1234">
    <a:tr><a:tc a:rsidR="5678"><a:p><a:r><a:t>R² &amp; RMSE</a:t></a:r></a:p></a:tc>
    <a:tc><a:p><a:r><a:t>0.6372</a:t></a:r></a:p></a:tc></a:tr>
    </a:tbl></a:body></a:document>'''
    with zipfile.ZipFile(doc, "w") as archive:
        archive.writestr("word/document.xml", body)
    assert "R² & RMSE | 0.6372" in read_any(doc)


def test_word_table_content_controls_do_not_hide_data(tmp_path):
    cells = '<w:tc><w:p><w:r><w:t>样本量</w:t></w:r></w:p></w:tc>'
    value = '<w:tc><w:p><w:r><w:t>120</w:t></w:r></w:p></w:tc>'
    cases = [
        '<w:tr>' + cells + value + '</w:tr>',
        '<w:sdt><w:sdtContent><w:tr>' + cells + value + '</w:tr></w:sdtContent></w:sdt>',
        '<w:tr>' + cells + '<w:sdt><w:sdtContent>' + value + '</w:sdtContent></w:sdt></w:tr>',
    ]
    for index, rows in enumerate(cases):
        doc = tmp_path / f'control-{index}.docx'
        with zipfile.ZipFile(doc, 'w') as archive:
            archive.writestr('word/document.xml', f'<w:document xmlns:w="{W}"><w:body><w:tbl>{rows}</w:tbl></w:body></w:document>')
        assert read_any(doc).strip() == '样本量 | 120'


def test_nested_table_rows_do_not_become_outer_rows(tmp_path):
    doc = tmp_path / 'nested.docx'
    body = f'''<w:document xmlns:w="{W}"><w:body><w:tbl><w:tr>
    <w:tc><w:p><w:r><w:t>外表标签</w:t></w:r></w:p></w:tc>
    <w:tc><w:sdt><w:sdtContent><w:tbl><w:tr><w:tc>
    <w:p><w:r><w:t>内表数据 120</w:t></w:r></w:p>
    </w:tc></w:tr></w:tbl></w:sdtContent></w:sdt></w:tc>
    </w:tr></w:tbl></w:body></w:document>'''
    with zipfile.ZipFile(doc, 'w') as archive:
        archive.writestr('word/document.xml', body)
    text = read_any(doc)
    assert text.count('内表数据 120') == 1
    assert text.strip() == '外表标签 | 内表数据 120'
