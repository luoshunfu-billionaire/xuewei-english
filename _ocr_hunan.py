# -*- coding: utf-8 -*-
"""OCR 扫描版湖南真题/模拟卷 -> _tmp_extract/*.txt"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pypdfium2 as pdfium
from rapidocr_onnxruntime import RapidOCR

sys.stdout.reconfigure(encoding='utf-8')

BASE = Path(__file__).resolve().parent
OUT_DIR = BASE / '_tmp_extract'
OUT_DIR.mkdir(exist_ok=True)

TARGETS = [
    BASE / '湖南省学位英语资料' / '湖南省学位英语资料' / '2021年学位英语真题(1).pdf',
    BASE / '湖南省学位英语资料' / '湖南省学位英语资料' / '2021年学位英语真题参考答案(1).pdf',
    BASE / '湖南省学位英语资料' / '湖南省学位英语资料' / '2022年学位英语真题试卷(4).pdf',
    BASE / '湖南省学位英语资料' / '湖南省学位英语资料' / '2022年学位英语真题试卷参考答案(4).pdf',
    BASE / '湖南省学位英语资料' / '湖南省学位英语资料' / '全真模拟试卷一(1).pdf',
    BASE / '湖南省学位英语资料' / '湖南省学位英语资料' / '全真模拟试卷参考答案一(1).pdf',
    BASE / '湖南省学位英语资料' / '湖南省学位英语资料' / '全真模拟试卷二.pdf',
    BASE / '湖南省学位英语资料' / '湖南省学位英语资料' / '全真模拟试卷参考答案二.pdf',
    BASE / '湖南省学位英语资料' / '湖南省学位英语资料' / '全真模拟试卷三.pdf',
    BASE / '湖南省学位英语资料' / '湖南省学位英语资料' / '全真模拟试卷参考答案三.pdf',
    BASE / '湖南省学位英语资料' / '湖南省学位英语资料' / '全真模拟试卷（四）.pdf',
    BASE / '湖南省学位英语资料' / '湖南省学位英语资料' / '全真模拟试卷参考答案（四）.pdf',
    BASE / '湖南省学位英语资料' / '湖南省学位英语资料' / '全真模拟试卷（五）.pdf',
    BASE / '湖南省学位英语资料' / '湖南省学位英语资料' / '全真模拟试卷参考答案（五）.pdf',
    BASE / '湖南省学位英语资料' / '湖南省学位英语资料' / '全真模拟试卷（六）.pdf',
    BASE / '湖南省学位英语资料' / '湖南省学位英语资料' / '全真模拟试卷参考答案（六）.pdf',
]


def _sorted_lines(result, landscape: bool) -> list[str]:
    """按页面方向恢复阅读顺序。

    纵向单列页(2021 真题)：直接按行(y 桶) + x 排序。
    横向双列页(模拟卷)：按 x 间隙分列，列内按 y，列间从左到右。
    """
    if not result:
        return []
    items = []
    for it in result:
        box, txt = it[0], it[1]
        if not txt:
            continue
        ys = [p[1] for p in box]
        xs = [p[0] for p in box]
        items.append((min(ys), min(xs), txt))

    if not landscape:
        items.sort(key=lambda t: (round(t[0] / 15), t[1]))
        return [t[2] for t in items]

    # 横向：按 x 聚类分列，相邻 x 间隙 > 120 视为新列
    items_by_x = sorted(items, key=lambda t: t[1])
    cols: list[list[tuple]] = []
    for it in items_by_x:
        if not cols:
            cols.append([it])
            continue
        if it[1] - cols[-1][-1][1] > 120:
            cols.append([it])
        else:
            cols[-1].append(it)
    out_lines: list[str] = []
    for col in cols:
        col.sort(key=lambda t: (round(t[0] / 15), t[1]))
        out_lines.extend(t[2] for t in col)
    return out_lines


def ocr_pdf(path: Path, scale: float = 2.0) -> str:
    ocr = RapidOCR()
    doc = pdfium.PdfDocument(str(path))
    chunks = []
    for i in range(len(doc)):
        page = doc[i]
        w, h = page.get_size()
        landscape = w > h
        bitmap = page.render(scale=scale)
        pil = bitmap.to_pil()
        tmp = OUT_DIR / f'_page_{i}.png'
        pil.save(tmp)
        result, _ = ocr(str(tmp))
        lines = _sorted_lines(result, landscape)
        page_text = '\n'.join(lines)
        chunks.append(f'--- page {i+1} ---\n{page_text}')
        print(f'  page {i+1}/{len(doc)} {("LAND" if landscape else "port")} chars={len(page_text)}')
        try:
            tmp.unlink()
        except Exception:
            pass
    return '\n\n'.join(chunks)


def main():
    for path in TARGETS:
        if not path.exists():
            print('MISSING', path.name)
            continue
        out = OUT_DIR / (path.stem + '.ocr.txt')
        if out.exists() and out.stat().st_size > 500:
            print('SKIP exists', out.name)
            continue
        print('OCR', path.name)
        try:
            text = ocr_pdf(path)
            out.write_text(text, encoding='utf-8')
            print('  ->', out.name, 'total', len(text))
        except Exception as e:
            print('  FAIL', e)


if __name__ == '__main__':
    main()
