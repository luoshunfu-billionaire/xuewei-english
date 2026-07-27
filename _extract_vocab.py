# -*- coding: utf-8 -*-
"""从词汇表 PDF OCR 提取词条 -> vocab.json (按行对齐版)"""
import fitz, json, re, sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from rapidocr_onnxruntime import RapidOCR

BASE = r'E:\software\weixin\xwechat_files\wxid_puzz4ob4e4l922_5bc3\msg\file\2026-07\学位英语\学位英语'
PDF = os.path.join(BASE, '学位英语资料', '学位英语资料', '4.学位英语词汇表(完整版).pdf')
OUT = os.path.join(BASE, 'vocab.json')
TMP = os.path.join(BASE, '_tmp_pages')
os.makedirs(TMP, exist_ok=True)

def has_cjk(s):
    return any('一' <= c <= '鿿' for c in s)

def is_word(s):
    return bool(re.fullmatch(r"[A-Za-z][A-Za-z\-']*", s.strip()))

def is_pos(s):
    return bool(re.fullmatch(r'((vt|vi|n|a|ad|prep|conj|pron|num|int|art|v)&?\.?\s*)+', s.strip()))

ocr = RapidOCR()
doc = fitz.open(PDF)
entries = []
for pno in range(doc.page_count):
    png = os.path.join(TMP, f'v{pno}.png')
    doc[pno].get_pixmap(dpi=150).save(png)
    result, _ = ocr(png)
    page_w = doc[pno].rect.width * 150 / 72
    # 收集碎片 (栏, cx, cy, text)
    frags = []
    for box, text, conf in result:
        xs = [pt[0] for pt in box]; ys = [pt[1] for pt in box]
        cx, cy = sum(xs)/4, sum(ys)/4
        t = text.strip()
        if not t or '学位英语词汇' in t or re.match(r'^\d+页，共\d+页$', t):
            continue
        frags.append([0 if cx < page_w/2 else 1, cx, cy, t])
    # 每栏按 y 聚成行 (容差 12px)
    rows = []
    for col in (0, 1):
        fs = sorted([f for f in frags if f[0] == col], key=lambda f: f[2])
        cur_row = []
        for f in fs:
            if cur_row and abs(f[2] - cur_row[-1][2]) > 12:
                rows.append(cur_row); cur_row = []
            cur_row.append(f)
        if cur_row: rows.append(cur_row)
    # 行内按 x 排序, 解析 word/pos/meaning
    for row in rows:
        row.sort(key=lambda f: f[1])
        word, pos, mean = None, [], []
        for _, _, _, t in row:
            if word is None and is_word(t):
                word = t
            elif is_pos(t):
                pos.append(t)
            elif has_cjk(t) or (word is not None):
                mean.append(t)
        if word:
            entries.append({'w': word, 'pos': ' '.join(pos), 'm': ' '.join(mean)})
        elif mean and entries:
            entries[-1]['m'] += ' '.join(mean)
    print(f'page {pno+1}/{doc.page_count} -> total {len(entries)}')

clean = []
for e in entries:
    e['m'] = re.sub(r'\s+', ' ', e['m']).strip()
    e['pos'] = re.sub(r'\s+', ' ', e['pos']).strip()
    if e['m'] and has_cjk(e['m']):
        clean.append(e)
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(clean, f, ensure_ascii=False, indent=1)
print(f'DONE: {len(clean)} entries')
for e in clean[:8] + clean[-4:]:
    print(e)
