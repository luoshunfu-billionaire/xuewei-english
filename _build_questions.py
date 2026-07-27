# -*- coding: utf-8 -*-
"""从本地 PDF 文字层提取选择题 -> questions.json

覆盖：
- 学位英语资料/考试试题（一）～（五）中的对话/阅读/词汇语法选择题
- 保留已有 questions.json 中的 2022 真题条目（若 PDF 为扫描件无法提取）

说明：湖南省真题/模拟卷多为扫描件，本脚本无法直接读字；
若之后装好 OCR，可再扩展。
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from pypdf import PdfReader

sys.stdout.reconfigure(encoding='utf-8')

BASE = Path(__file__).resolve().parent
OUT = BASE / 'questions.json'
MAT = BASE / '学位英语资料' / '学位英语资料'

NOISE = re.compile(
    r'51升学网程薇老师|考试须知|请考生|答题纸|Answer Sheet|试卷一|试卷二|'
    r'字迹清晰|一律判为|监考老师|Directions:.*?(?=\n\d+\.|\nPart|\nDialogue|\nPassage|\nSpeaker)',
    re.I | re.S,
)

PART_MAP = {
    'dialogue': '完成对话',
    'reading': '阅读理解',
    'grammar': '词汇语法',
}


def pdf_text(path: Path) -> str:
    r = PdfReader(str(path))
    parts = []
    for p in r.pages:
        t = p.extract_text() or ''
        parts.append(t)
    text = '\n'.join(parts)
    text = text.replace('\xa0', ' ').replace('\u3000', ' ')
    text = re.sub(r'[ \t]+\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


def clean(s: str) -> str:
    s = NOISE.sub('', s)
    s = re.sub(r'[ \t]{2,}', ' ', s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s.strip()


def parse_answer_key_block(text: str) -> dict[int, str]:
    """解析答案表，含 1. A 2. B 以及 11-25. ACDCA BCADD ABDBB 压缩格式。"""
    answers: dict[int, str] = {}
    m = re.search(
        r'(样卷参考答案|试题答案|外语水平考试试题答案|参考答案|Reading comprehension)',
        text,
        re.I,
    )
    blob = text[m.start():] if m else text

    for a, b, letters in re.findall(
        r'(\d{1,2})\s*[-–—]\s*(\d{1,2})\s*[\.、．]?\s*([A-Da-d\s]+)', blob
    ):
        start, end = int(a), int(b)
        letters = re.sub(r'[^A-Da-d]', '', letters).upper()
        if end - start + 1 == len(letters):
            for i, ch in enumerate(letters):
                answers[start + i] = ch

    for num, letter in re.findall(r'(\d{1,2})\s*[\.、．]?\s*([A-Da-d])\b', blob):
        n = int(num)
        if 1 <= n <= 80 and n not in answers:
            answers[n] = letter.upper()
    return answers


def parse_explained_answers(text: str) -> tuple[dict[int, str], dict[int, str]]:
    """解析带解析的答案：'1. A 说话人…' / '16. C 单词释义题…'"""
    answers: dict[int, str] = {}
    exps: dict[int, str] = {}
    m = re.search(r'(样卷参考答案|试题答案|外语水平考试试题答案|参考答案|PART II Reading|PartⅡ|Part II)', text)
    # Prefer the answer section near the end for papers that embed explanations
    # Find blocks like: 1. A 中文解析
    for num, letter, rest in re.findall(
        r'(?ms)^(\d{1,2})\s*[\.、．]\s*([A-Da-d])\s+(.+?)(?=^\d{1,2}\s*[\.、．]\s*[A-Da-d]\s+|\Z)',
        text,
    ):
        n = int(num)
        if not (1 <= n <= 80):
            continue
        answers[n] = letter.upper()
        exp = clean(rest)
        exp = re.sub(r'\s+', ' ', exp)
        if len(exp) > 8:
            exps[n] = exp[:400]
    # Also plain key lines
    for n, letter in parse_answer_key_block(text).items():
        answers.setdefault(n, letter)
    return answers, exps


def split_options(block: str) -> dict[str, str] | None:
    """从题干后文本解析 A/B/C/D 选项。"""
    block = (
        block.replace('A)', 'A.').replace('B)', 'B.').replace('C)', 'C.').replace('D)', 'D.')
        .replace('A）', 'A.').replace('B）', 'B.').replace('C）', 'C.').replace('D）', 'D.')
    )
    matches = list(re.finditer(r'(?:(?<=\s)|^)([A-D])[\.、．]\s*', block))
    if len(matches) < 4:
        return None
    best = None
    for i in range(len(matches) - 3):
        seq = [matches[i + k].group(1) for k in range(4)]
        if seq == ['A', 'B', 'C', 'D']:
            best = matches[i:i + 4]
            break
    if not best:
        return None
    opts = {}
    for j, m in enumerate(best):
        start = m.end()
        end = best[j + 1].start() if j < 3 else len(block)
        val = block[start:end].strip()
        val = re.sub(r'\s+', ' ', val)
        val = re.split(
            r'(?i)(?:\bPart\s+[IVXLCⅠⅡⅢⅣⅤ]+|\bPassage\s+\w+|\bSection\s+[A-Z]|\bDialogue\s+\w+|\d{1,2}\s*[\.、．])',
            val,
        )[0].strip(' ;；')
        opts[m.group(1)] = val
    if any(len(opts.get(k, '')) < 1 for k in 'ABCD'):
        return None
    return opts


def extract_numbered_mcqs(body: str) -> dict[int, tuple[str, dict[str, str]]]:
    """提取 1. stem... A. B. C. D. 结构。"""
    body = clean(body)
    # Split by question numbers at line starts
    chunks = re.split(r'(?m)(?=^\s*\d{1,2}\s*[\.、．]\s*)', body)
    out: dict[int, tuple[str, dict[str, str]]] = {}
    for ch in chunks:
        m = re.match(r'\s*(\d{1,2})\s*[\.、．]\s*(.*)', ch, re.S)
        if not m:
            continue
        n = int(m.group(1))
        rest = m.group(2).strip()
        # Find options start
        om = re.search(r'(?m)(?:^|\n)\s*[A][\.、．\)]\s*', rest)
        if not om:
            # options maybe inline after stem
            om = re.search(r'\sA[\.、．\)]\s*', rest)
        if not om:
            continue
        stem = rest[:om.start()].strip()
        stem = re.sub(r'\s+', ' ', stem)
        opts = split_options(rest[om.start():])
        if not opts:
            continue
        # Trim stem bleed
        stem = re.sub(r'(?i)\bDirections:.*', '', stem).strip()
        if len(stem) < 3:
            continue
        out[n] = (stem, opts)
    return out


def extract_passages(body: str) -> list[tuple[str, str]]:
    """返回 [(title, passage_text), ...]。"""
    body = clean(body)
    parts = re.split(r'(?i)(?=Passage\s+(?:One|Two|Three|Four|1|2|3|4|[IVX]+))', body)
    passages = []
    for p in parts:
        m = re.match(r'(?is)(Passage\s+\w+)\s*(.*)', p)
        if not m:
            continue
        title = m.group(1).strip()
        text = m.group(2)
        # cut at first question number typical for reading (11. or Questions)
        text = re.split(r'(?m)^\s*(?:Questions?\s+\d+|^\s*11\s*[\.、．])', text)[0]
        text = re.sub(r'\s+', ' ', text).strip()
        if len(text) > 80:
            passages.append((title, text))
    return passages


def attach_passage(stem: str, n: int, passages: list[tuple[str, str]]) -> str:
    if not passages:
        return stem
    # heuristic: 5 questions per passage starting at 11,16,21,26 or 11,16,21
    # find which passage by index
    idx = 0
    if n >= 11:
        idx = (n - 11) // 5
    if idx >= len(passages):
        idx = len(passages) - 1
    title, text = passages[idx]
    # keep passage shorter for UI
    if len(text) > 1200:
        text = text[:1200] + '…'
    return f'【{title}】\n{text}\n\n{stem}'


def parse_blank_dialogues(body: str) -> dict[int, tuple[str, dict[str, str]]]:
    """湖南卷式：Dialogue One + 共享选项，空格题号 1-10。"""
    out: dict[int, tuple[str, dict[str, str]]] = {}
    body = clean(body)
    dialogs = re.split(r'(?=Dialogue\s+(?:One|Two|Three|1|2|3))', body, flags=re.I)
    for d in dialogs:
        if not re.match(r'Dialogue', d, re.I):
            continue
        # options block: lines starting with A. after dialogue
        om = re.search(r'(?m)^\s*A[\.、．\)]\s+', d)
        if not om:
            continue
        dialogue = d[:om.start()].strip()
        opts = split_options(d[om.start():])
        if not opts:
            continue
        # blanks as standalone numbers in dialogue
        nums = [int(x) for x in re.findall(r'(?:^|\s)(\d{1,2})(?=\s|[A-Za-z“"‘\.]|$)', dialogue)
                if 1 <= int(x) <= 10]
        # better: numbers that look like blanks - often just "1" "2" on their own in line
        nums = [int(x) for x in re.findall(r'(?<!\d)([1-9]|10)(?!\d)', dialogue)]
        # unique preserve order
        seen = []
        for n in nums:
            if n not in seen and 1 <= n <= 10:
                seen.append(n)
        for n in seen:
            stem = re.sub(rf'(?<!\d){n}(?!\d)', f'【{n}】______', dialogue, count=1)
            stem = re.sub(r'\s+', ' ', stem).strip()
            out[n] = (stem, opts)
    return out


def build_from_paper(src: str, text: str, style: str) -> list[dict]:
    answers, exps = parse_explained_answers(text)
    plain = parse_answer_key_block(text)
    for k, v in plain.items():
        answers.setdefault(k, v)

    # Split body vs answer section
    am = re.search(r'(样卷参考答案|外语水平考试试题答案|试题答案\s*$|参考答案\s*$)', text, re.M)
    body = text[:am.start()] if am else text

    items: list[dict] = []

    if style == 'blank_dialogue':
        mcqs = parse_blank_dialogues(body)
        # also numbered reading/vocab after dialogue section
        # remove dialogue parts for numbered extract
        rest = re.split(r'(?i)Part\s*II|Part\s*Ⅱ|Reading Comprehension', body, maxsplit=1)
        rest_body = rest[1] if len(rest) > 1 else body
        numbered = extract_numbered_mcqs(rest_body)
        passages = extract_passages(rest_body)
        for n, (stem, opts) in numbered.items():
            mcqs[n] = (attach_passage(stem, n, passages) if n >= 11 and n <= 30 else stem, opts)
    else:
        mcqs = extract_numbered_mcqs(body)
        passages = extract_passages(body)
        for n in list(mcqs.keys()):
            if 11 <= n <= 35:
                stem, opts = mcqs[n]
                mcqs[n] = (attach_passage(stem, n, passages), opts)

    for n, (stem, opts) in sorted(mcqs.items()):
        ans = answers.get(n)
        if not ans or ans not in opts:
            # still keep with empty? skip without answer to avoid wrong practice
            continue
        if n <= 15 or (style == 'blank_dialogue' and n <= 10):
            part, typ = '完成对话', 'dialogue'
        elif n <= 30 or (max(mcqs) >= 40 and n <= 35):
            # reading usually 11-30 or 16-35
            if n <= 15 and style != 'blank_dialogue':
                part, typ = '完成对话', 'dialogue'
            elif n < 31 or (n <= 35 and any(k >= 31 for k in mcqs)):
                if n <= 30:
                    part, typ = '阅读理解', 'reading'
                else:
                    part, typ = '词汇语法', 'grammar'
            else:
                part, typ = '词汇语法', 'grammar'
        else:
            part, typ = '词汇语法', 'grammar'

        # refine part ranges by paper style
        if style == 'blank_dialogue':
            if n <= 10:
                part, typ = '完成对话', 'dialogue'
            elif n <= 30:
                part, typ = '阅读理解', 'reading'
            else:
                part, typ = '词汇语法', 'grammar'
        else:
            # paper 17/19: 1-15 dialogue, 16-35 reading?, then vocab
            # paper 18: 1-10 dialogue, 11-? reading
            if '试题（二）' in src or '试题(二)' in src:
                if n <= 10:
                    part, typ = '完成对话', 'dialogue'
                elif n <= 25:
                    part, typ = '阅读理解', 'reading'
                else:
                    part, typ = '词汇语法', 'grammar'
            else:
                if n <= 15:
                    part, typ = '完成对话', 'dialogue'
                elif n <= 35:
                    part, typ = '阅读理解', 'reading'
                else:
                    part, typ = '词汇语法', 'grammar'

        qid = f"{src}-{n}"
        items.append({
            'id': re.sub(r'\s+', '', qid),
            'src': src,
            'part': part,
            'type': typ,
            'stem': stem,
            'options': opts,
            'answer': ans,
            'exp': exps.get(n, f'正确答案：{ans}'),
        })
    return items


def main():
    papers = [
        ('考试试题（一）', MAT / '17.学位英语考试试题（一）答案.pdf', 'standard'),
        ('考试试题（二）', MAT / '18.学位英语考试试题（二）及答案.pdf', 'standard'),
        ('考试试题（三）', MAT / '19.学位英语考试试题（三）及答案.pdf', 'standard'),
        ('考试试题（四）', MAT / '20.学位英语考试试题（四）及答案.pdf', 'blank_dialogue'),
        ('考试试题（五）', MAT / '21.学位英语考试试题（五）及答案.pdf', 'blank_dialogue'),
    ]

    all_q: list[dict] = []
    # keep existing 2022 handcrafted items
    if OUT.exists():
        old = json.loads(OUT.read_text(encoding='utf-8'))
        for q in old:
            if '2022' in q.get('src', '') or q.get('id', '').startswith('2022'):
                all_q.append(q)
        print(f'kept existing 2022 items: {len(all_q)}')

    seen_ids = {q['id'] for q in all_q}

    for src, path, style in papers:
        if not path.exists():
            print('MISSING', path)
            continue
        text = pdf_text(path)
        items = build_from_paper(src, text, style)
        added = 0
        for q in items:
            if q['id'] in seen_ids:
                continue
            seen_ids.add(q['id'])
            all_q.append(q)
            added += 1
        print(f'{src}: extracted {len(items)}, added {added}')

    # stats
    by_src: dict[str, int] = {}
    by_part: dict[str, int] = {}
    for q in all_q:
        by_src[q['src']] = by_src.get(q['src'], 0) + 1
        by_part[q['part']] = by_part.get(q['part'], 0) + 1

    OUT.write_text(json.dumps(all_q, ensure_ascii=False, indent=1), encoding='utf-8')
    print('TOTAL', len(all_q))
    print('by_src', by_src)
    print('by_part', by_part)


if __name__ == '__main__':
    main()
