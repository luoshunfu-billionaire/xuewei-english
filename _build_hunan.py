# -*- coding: utf-8 -*-
"""从 OCR 文本（_tmp_extract/*.ocr.txt）解析湖南真题/模拟卷 -> 追加到 questions.json

覆盖：
- 2021 年学位英语真题
- 全真模拟试卷一 ~ 六

只收选择题（完成对话/阅读理解/词汇语法），完形填空/翻译/作文无 ABCD 选项的会被
split_options 自然过滤。答案来自独立的答案文件，格式两种：
  - 1. D          (题号 + 分隔 + 字母，模拟卷)
  - 1.【答案】D。  (2021 真题及解析)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# 复用 _build_questions.py 的底层解析函数
from _build_questions import (
    clean,
    split_options,
    extract_numbered_mcqs,
    extract_passages,
    parse_blank_dialogues,
    attach_passage,
)

sys.stdout.reconfigure(encoding='utf-8')

BASE = Path(__file__).resolve().parent
OCR = BASE / '_tmp_extract'
OUT = BASE / 'questions.json'

# 湖南卷式：1-10 完成对话，11-30 阅读理解，31-50 词汇语法（个别卷阅读到 35）
DIALOGUE_MAX = 10
READING_MAX = 35

# OCR 噪声：页眉页脚、分页标记、答题说明残留
PAGE_MARK = re.compile(r'---\s*page\s*\d+\s*---')
HUNAN_NOISE = re.compile(
    r'成人高等教育学士学位英语考试|全真模拟试卷[（(][一二三四五六][）)](?:第\d+页[（(]共\d+页[）)])?|'
    r'\d{4}年真题(?:第\d+页[（(]共\d+页[）)])?|（考试时间\d+分钟）|ANSWTRSE|ANSWERSE|'
    r'^\s*\d{4}\s*$',  # 单独的年份行（如 9882）
    re.I | re.M,
)


def hunan_clean(s: str) -> str:
    s = PAGE_MARK.sub('\n', s)
    s = HUNAN_NOISE.sub('', s)
    s = clean(s)
    return s


# 选项尾部泄漏裁剪：切掉混进来的下一个选项标记或下题内容
OPT_LEAK = re.compile(r'\s+[A-D][\.、．]\s+\S')
# 完形填空段落污染特征
CLOZE_MARK = re.compile(r'Vocabulary\s*and\s*Structure|My\s+father\s+was\s+a\s+foreman|'
                         r'Part\s*II\s*Vocabulary|Cloze', re.I)


def trim_option(val: str) -> str:
    """裁掉选项尾部混入的下题内容/泄漏选项标记。"""
    val = re.sub(r'\s+', ' ', val).strip()
    m = OPT_LEAK.search(val)
    if m and m.start() > 3:
        val = val[:m.start()].strip()
    # 去掉尾部粘连的下题题干片段（以大写字母开头的新句子且明显无关时截断）
    val = re.split(r'\s{2,}', val)[0].strip()
    if len(val) > 90:
        val = val[:90].rstrip()
    return val


def is_clean_question(q: dict) -> bool:
    """质量过滤：丢弃被 OCR 污染的题目。"""
    stem = q['stem']
    if len(stem) < 15 or len(stem) > 220:
        return False
    if CLOZE_MARK.search(stem):
        return False
    opts = q['options']
    for k in 'ABCD':
        v = opts.get(k, '')
        if len(v) < 1 or len(v) > 90:
            return False
        # 完形填空段落正文泄进选项
        if CLOZE_MARK.search(v):
            return False
    return True


def parse_answers(answer_text: str) -> tuple[dict[int, str], dict[int, str]]:
    """解析湖南答案文件，返回 (answers, explanations)。

    兼容格式：
      1. D            模拟卷：题号+分隔+字母，后跟换行/解析
      1.【答案】D。   2021：题号+【答案】+字母
      8.A            紧贴
    """
    answers: dict[int, str] = {}
    exps: dict[int, str] = {}

    # 格式一：N.【答案】X。  或 N.[答案]X  （半/全角括号，可能缺左括号）
    for num, letter, rest in re.findall(
        r'(?ms)\b(\d{1,2})\s*[\.、．]?\s*[【\[]?\s*答案\s*[\】\]]?\s*([A-Da-d])\s*[。.．]?\s*(.+?)(?=^\s*\d{1,2}\s*[\.、．]?\s*[【\[]?\s*答案|\Z)',
        answer_text,
    ):
        n = int(num)
        if not (1 <= n <= 80):
            continue
        answers[n] = letter.upper()
        exp = hunan_clean(rest)
        exp = re.sub(r'\s+', ' ', exp).strip()
        if len(exp) > 8:
            exps[n] = exp[:400]

    # 格式二：行首 N.X  （题号+分隔+字母，字母后须跟换行或非字母，避免误匹配 N.D 形如 '2.D' 内的正文）
    for num, letter in re.findall(
        r'(?m)^\s*(\d{1,2})\s*[\.、．]\s*([A-Da-d])(?![A-Da-d])',
        answer_text,
    ):
        n = int(num)
        if 1 <= n <= 80 and n not in answers:
            answers[n] = letter.upper()

    # 格式三：紧贴 N X 但无分隔符的行：^8A  （少数 OCR 把点吞掉）
    for num, letter in re.findall(r'(?m)^\s*(\d{1,2})([A-Da-d])(?![A-Da-d])\s*$', answer_text):
        n = int(num)
        if 1 <= n <= 80 and n not in answers:
            answers[n] = letter.upper()

    return answers, exps


def build_paper(src: str, paper_text: str, answer_text: str) -> list[dict]:
    answers, exps = parse_answers(answer_text)

    body = hunan_clean(paper_text)

    # 完成对话（1-10）：Dialogue + 共享选项 + 空格题号
    dialogues = parse_blank_dialogues(body)

    # 阅读与词汇语法：去掉对话部分后的正文
    rest_parts = re.split(r'(?i)Part\s*II|Part\s*Ⅱ|Reading\s*Comprehension', body, maxsplit=1)
    rest_body = rest_parts[1] if len(rest_parts) > 1 else body
    numbered = extract_numbered_mcqs(rest_body)
    passages = extract_passages(rest_body)

    # 合并：对话题号 1-10，其余走 numbered
    mcqs: dict[int, tuple[str, dict[str, str]]] = {}
    for n, (stem, opts) in dialogues.items():
        mcqs[n] = (stem, opts)
    for n, (stem, opts) in numbered.items():
        if n in mcqs:
            continue
        if READING_MAX - 4 <= n <= READING_MAX:
            stem = attach_passage(stem, n, passages)
        mcqs[n] = (stem, opts)

    items: list[dict] = []
    for n, (stem, opts) in sorted(mcqs.items()):
        ans = answers.get(n)
        if not ans or ans not in opts:
            continue  # 无答案或答案不在选项内，丢弃避免错题
        # 裁剪每个选项尾部泄漏
        opts = {k: trim_option(v) for k, v in opts.items()}
        if n <= DIALOGUE_MAX:
            part, typ = '完成对话', 'dialogue'
        elif n <= READING_MAX:
            part, typ = '阅读理解', 'reading'
        else:
            part, typ = '词汇语法', 'grammar'
        qid = re.sub(r'\s+', '', f'{src}-{n}')
        q = {
            'id': qid,
            'src': src,
            'part': part,
            'type': typ,
            'stem': stem,
            'options': opts,
            'answer': ans,
            'exp': exps.get(n, f'正确答案：{ans}'),
        }
        if not is_clean_question(q):
            continue
        items.append(q)
    return items


# src -> (paper ocr stem, answer ocr stem)
PAPERS = [
    ('2021真题', '2021年学位英语真题(1)', '2021年学位英语真题参考答案(1)'),
    ('全真模拟试卷一', '全真模拟试卷一(1)', '全真模拟试卷参考答案一(1)'),
    ('全真模拟试卷二', '全真模拟试卷二', '全真模拟试卷参考答案二'),
    ('全真模拟试卷三', '全真模拟试卷三', '全真模拟试卷参考答案三'),
    ('全真模拟试卷四', '全真模拟试卷（四）', '全真模拟试卷参考答案（四）'),
    ('全真模拟试卷五', '全真模拟试卷（五）', '全真模拟试卷参考答案（五）'),
    ('全真模拟试卷六', '全真模拟试卷（六）', '全真模拟试卷参考答案（六）'),
]


def main():
    all_q: list[dict] = []
    if OUT.exists():
        all_q = json.loads(OUT.read_text(encoding='utf-8'))
        print(f'已有题目: {len(all_q)}')

    seen_ids = {q['id'] for q in all_q}

    for src, paper_stem, ans_stem in PAPERS:
        paper_fp = OCR / (paper_stem + '.ocr.txt')
        ans_fp = OCR / (ans_stem + '.ocr.txt')
        if not paper_fp.exists() or not ans_fp.exists():
            print(f'MISSING  {src}: {paper_stem} / {ans_stem}')
            continue
        paper_text = paper_fp.read_text(encoding='utf-8')
        answer_text = ans_fp.read_text(encoding='utf-8')
        items = build_paper(src, paper_text, answer_text)
        added = 0
        for q in items:
            if q['id'] in seen_ids:
                continue
            seen_ids.add(q['id'])
            all_q.append(q)
            added += 1
        kept = [q for q in items if q['id'] in seen_ids]
        print(f'{src}: 解析 {len(items)} 题, 新增 {added}, 答案文件识别 {len(parse_answers(answer_text)[0])} 个答案')

    OUT.write_text(json.dumps(all_q, ensure_ascii=False, indent=1), encoding='utf-8')

    by_src: dict[str, int] = {}
    by_part: dict[str, int] = {}
    for q in all_q:
        by_src[q['src']] = by_src.get(q['src'], 0) + 1
        by_part[q['part']] = by_part.get(q['part'], 0) + 1
    print('--- by_src ---')
    for k, v in sorted(by_src.items()):
        print(f'  {k}: {v}')
    print('--- by_part ---')
    for k, v in sorted(by_part.items()):
        print(f'  {k}: {v}')
    print('TOTAL', len(all_q))


if __name__ == '__main__':
    main()
