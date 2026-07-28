# -*- coding: utf-8 -*-
"""把剩余复习资料（语法/搭配/同位词/知识点/完形/翻译/作文）解析成 study.json

输入：_tmp_extract/*.txt（由 pypdf / OCR 提取）
输出：study.json —— { modules: [...] }

模块 kind：
  article —— sections: [{t, body}]   章节阅读（语法、知识点、金句、模板）
  pairs   —— items: [{en, cn}]       英中对照（搭配、同位词、完形词汇）
           或 groups: [{t, items}]   分组对照（翻译300句、万能句型）
  essays  —— items: [{t, body}]      范文
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

BASE = Path(__file__).resolve().parent
EXT = BASE / '_tmp_extract'
OUT = BASE / 'study.json'

CN = '一-鿿'
ASCII_RUN = re.compile(r'[A-Za-z]')


def read(name: str) -> str:
    return (EXT / name).read_text(encoding='utf-8')


def tidy(s: str) -> str:
    """通用清理：统一空白、压缩空行、去掉图标字体私用区字符。"""
    s = s.replace('\xa0', ' ').replace('　', ' ')
    s = re.sub('[\ue000-\uf8ff•]', '', s)  # 图标字体私用区+项目符号
    s = re.sub(r'[ \t]+\n', '\n', s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s.strip()


NUM_GROUP = re.compile(r'(?m)^\d{1,4}\s*[.、]\s*\S')


def chunk_long_sections(secs, max_chars=14000):
    """超长小节按编号组边界再切，避免一节几万字无法阅读。"""
    out = []
    for title, body in secs:
        if len(body) <= max_chars:
            out.append((title, body))
            continue
        cuts = [m.start() for m in NUM_GROUP.finditer(body)]
        if len(cuts) < 4:
            out.append((title, body))
            continue
        part, start, idx = [], 0, 1
        cur = 0
        for c in cuts[1:]:
            if c - start > max_chars:
                out.append((f'{title}（{idx}）', tidy(body[start:c])))
                idx += 1
                start = c
            cur = c
        out.append((f'{title}（{idx}）', tidy(body[start:])))
    return out


def strip_page_marks(s: str) -> str:
    s = re.sub(rf'^第\s*\d+\s*页\s*共\s*\d+\s*页\s*$', '', s, flags=re.M)
    s = re.sub(r'^-{2,}\s*page\s*\d+\s*-{2,}$', '', s, flags=re.M | re.I)
    return s


# ---------------------------------------------------------------- 文章切分

def split_by_headers(text: str, pat: re.Pattern, keep_intro=True):
    """按行级标题切分，返回 [(标题, 正文)]。标题前的内容归为 '导读'。"""
    lines = text.split('\n')
    heads = [i for i, ln in enumerate(lines) if pat.match(ln.strip())]
    secs = []
    if keep_intro and (not heads or heads[0] > 0):
        end = heads[0] if heads else len(lines)
        intro = tidy('\n'.join(lines[:end]))
        if intro:
            secs.append(('导读', intro))
    for j, h in enumerate(heads):
        end = heads[j + 1] if j + 1 < len(heads) else len(lines)
        body = tidy('\n'.join(lines[h + 1:end]))
        secs.append((lines[h].strip(), body))
    return secs


def article_mod(mid, cat, title, src_note, secs):
    return {
        'id': mid, 'cat': cat, 'title': title, 'kind': 'article',
        'src': src_note,
        'sections': [{'t': t, 'body': b} for t, b in secs if b or t],
    }


# ---------------------------------------------------------------- 各资料解析

def parse_grammar_a():
    """2.语法复习（上）：按「第X节」切，第二章起按「第X章」。"""
    t = tidy(strip_page_marks(read('2.学位英语语法复习资料（上）.txt')))
    pat = re.compile(r'^第[一二三四五六七八九十]+节\s*[^\n]{0,30}$')
    secs = split_by_headers(t, pat)
    return article_mod('grammar-a', '语法', '语法复习（上）·重点串讲',
                       '2.学位英语语法复习资料（上）.pdf', secs)


def parse_grammar_b():
    """3.语法复习（下）：语法体系图表，按空行大块切。"""
    t = tidy(strip_page_marks(read('3.学位英语语法复习资料（下）.txt')))
    t = re.sub(r'^[\s\r\n]*$', '', t, flags=re.M)
    # 以「名词/动词/形容词…」等词性大标题切分；找不到就整篇一节
    pat = re.compile(r'^学位?\s*英语语法体系.*$|^(名词|动词|形容词|副词|代词|介词|连词|冠词|数词|感叹词)\s*$')
    secs = split_by_headers(t, pat)
    if len(secs) <= 1:
        secs = [('英语语法体系', t)]
    return article_mod('grammar-b', '语法', '语法复习（下）·语法体系',
                       '3.学位英语语法复习资料（下）.pdf', secs)


def parse_knowledge():
    """7.知识点：按「第X部分」切。"""
    t = tidy(strip_page_marks(read('7.学位英语知识点(完整版).txt')))
    pat = re.compile(r'^第[一二三四五六七八九十百]+部分[：: ]?[^\n]{0,25}$')
    secs = chunk_long_sections(split_by_headers(t, pat))
    return article_mod('knowledge', '语法', '知识点（完整版）',
                       '7.学位英语知识点(完整版).pdf', secs)


def parse_mcq_core():
    """8.选择题核心：按「复习资料汇总 N：主题」切。"""
    t = tidy(strip_page_marks(read('8.学位英语选择题核心复习资料.txt')))
    pat = re.compile(r'^学位英语知识点复习资料汇总\s*\d+[：:]?\s*[^\n]{0,25}$')
    secs = split_by_headers(t, pat)
    out = [(re.sub(r'^学位英语知识点复习资料汇总\s*\d+[：:]\s*', '', h) or h, b)
           for h, b in secs]
    return article_mod('mcq-core', '语法', '选择题核心复习（短语语法要点）',
                       '8.学位英语选择题核心复习资料.pdf', out)


def parse_cloze_phrases():
    """9.完形填空词组：按「第X部分」切。"""
    t = tidy(strip_page_marks(read('9.学位英语完形填空词组(完整版).txt')))
    pat = re.compile(r'^第[一二三四五六七八九十百]+部分[：: ]?[^\n]{0,25}$')
    secs = chunk_long_sections(split_by_headers(t, pat))
    return article_mod('cloze-phrases', '短语词汇', '完形填空词组（完整版）',
                       '9.学位英语完形填空词组(完整版).pdf', secs)


# ---------------------------------------------------------------- 英中对照

PAIR_RE = re.compile(rf'^(?P<en>[A-Za-z][A-Za-z0-9 .\'\-()/&,;?!…]*?)\s+(?P<cn>[.…·]*[{CN}].*)$')


def parse_colloc():
    """5.固定搭配：每行「英文 中文」。无中文的行并入上一条。"""
    t = tidy(read('5.学位英语固定搭配（完整版）.txt'))
    items = []
    for ln in t.split('\n'):
        ln = ln.strip()
        if not ln or ln in ('学位英语 固定搭配', '学位英语固定搭配'):
            continue
        m = PAIR_RE.match(ln)
        if m:
            items.append({'en': m.group('en').strip(),
                          'cn': m.group('cn').strip(' .…·')})
        elif items:
            items[-1]['cn'] += ' ' + ln
    return {'id': 'colloc', 'cat': '短语词汇', 'title': '固定搭配（完整版）',
            'kind': 'pairs', 'src': '5.学位英语固定搭配（完整版）.pdf', 'items': items}


SYN_RE = re.compile(rf'^\d{{1,3}}\s*[.、,，]?\s*[a-zA-Z .、。:：*\-]{{0,8}}(?P<cn>[{CN}][^A-Za-z\n]{{0,20}}?)\s+(?P<en>[A-Za-z].*)$')


def parse_synonyms():
    """6.同位词300：「N.中文 英文1, 英文2」。"""
    t = tidy(read('6.学位英语同位词（300个）.txt'))
    items = []
    for ln in t.split('\n'):
        ln = ln.strip()
        if not ln or '同义词' in ln and len(ln) < 20:
            continue
        m = SYN_RE.match(ln)
        if m:
            items.append({'cn': m.group('cn').strip(' .。'),
                          'en': m.group('en').strip(' .')})
        elif items:
            items[-1]['en'] += ' ' + ln
    return {'id': 'synonyms', 'cat': '短语词汇', 'title': '同位词（300组）·写作替换',
            'kind': 'pairs', 'swap': True,
            'src': '6.学位英语同位词（300个）.pdf', 'items': items}


CLOZE_V_RE = re.compile(r'^\d{1,4}\s*[.、]\s*(?P<w>[A-Za-z][A-Za-z\-]*)\s+(?P<rest>.*)$')


def parse_cloze_vocab():
    """10.完形填空词汇：「N.word pos. 中文」。"""
    t = tidy(read('10.学位英语完形填空词汇（完整版）.txt'))
    items = []
    for ln in t.split('\n'):
        ln = ln.strip()
        m = CLOZE_V_RE.match(ln)
        if not m:
            if items and ln:
                items[-1]['cn'] += ' ' + ln
            continue
        rest = m.group('rest').strip()
        pm = re.match(rf'^(?P<pos>(?:[a-z]{{1,3}}\.|[a-z]{{1,3}},\s*)+)\s*(?P<cn>.*)$', rest)
        if pm:
            pos, cn = pm.group('pos').strip(' ,'), pm.group('cn').strip()
        else:
            pos, cn = '', rest
        items.append({'en': m.group('w'), 'pos': pos, 'cn': cn})
    return {'id': 'cloze-vocab', 'cat': '短语词汇', 'title': '完形填空高频词汇',
            'kind': 'pairs', 'src': '10.学位英语完形填空词汇（完整版）.pdf', 'items': items}


def split_cn_en(text: str):
    """把「中文。English sentence.」拆成 (cn, en)。找不到英文返回 None。"""
    m = re.match(rf'^(?P<cn>.*?[{CN}][^A-Za-z]*?)\s*(?P<en>[A-Za-z][\s\S]*)$', text)
    if not m:
        return None
    cn, en = m.group('cn').strip(), m.group('en').strip()
    if not ASCII_RUN.search(en):
        return None
    return cn, en


def parse_translate300():
    """11.英汉互译300句：「一、主题」分组 + 编号句对。"""
    t = tidy(read('11.学位英语英汉互译句法（完整版）.txt'))
    t = re.sub(r'(?m)^.*51升学网程薇老师.*$', '', t)
    groups, cur = [], None
    buf_num = None
    for ln in t.split('\n'):
        ln = ln.strip()
        if not ln:
            continue
        gm = re.match(r'^[一二三四五六七八九十]+、\s*(?P<t>[^\n]{1,25})$', ln)
        if gm:
            cur = {'t': gm.group('t'), 'items': []}
            groups.append(cur)
            continue
        if cur is None:
            continue
        nm = re.match(r'^(\d{1,3})\s*[.、]\s*(.*)$', ln)
        if nm:
            buf_num = nm.group(2)
            pair = split_cn_en(buf_num)
            if pair:
                cur['items'].append({'cn': pair[0], 'en': pair[1]})
                buf_num = None
            continue
        # 续行：可能是上一句的英文部分
        if buf_num is not None:
            joined = buf_num + ' ' + ln
            pair = split_cn_en(joined)
            if pair:
                cur['items'].append({'cn': pair[0], 'en': pair[1]})
                buf_num = None
            elif ASCII_RUN.match(ln):
                cur['items'].append({'cn': buf_num, 'en': ln})
                buf_num = None
            else:
                buf_num = joined
        elif cur['items'] and ASCII_RUN.match(ln) and not cur['items'][-1].get('en_done'):
            cur['items'][-1]['en'] += ' ' + ln
    groups = [g for g in groups if g['items']]
    return {'id': 'translate300', 'cat': '翻译', 'title': '英汉互译300句',
            'kind': 'pairs', 'src': '11.学位英语英汉互译句法（完整版）.pdf',
            'groups': groups}


def parse_patterns():
    """15.万能套用句型：「一）段首句」等分组 + 编号句（中文+英文）。"""
    t = tidy(read('15.学位英语作文万能套用句型.txt'))
    groups, cur = [], None
    pending_cn = None
    for ln in t.split('\n'):
        ln = ln.strip()
        if not ln or ln in ('学位英语万能模板',):
            continue
        gm = re.match(r'^[（(]?[一二三四五六七八九十]+[）)]\s*(?P<t>[^\n]{1,25})$', ln)
        if gm:
            title = gm.group('t')
            # 同名组（PDF分页重复标题）合并
            hit = next((g for g in groups if g['t'] == title), None)
            if hit:
                cur = hit
            else:
                cur = {'t': title, 'items': []}
                groups.append(cur)
            continue
        if cur is None:
            cur = {'t': '通用', 'items': []}
            groups.append(cur)
        nm = re.match(r'^(\d{1,3})\s*[.、]\s*(.*)$', ln)
        if nm:
            rest = nm.group(2)
            pair = split_cn_en(rest)
            if pair:
                cur['items'].append({'cn': pair[0], 'en': pair[1]})
            elif ASCII_RUN.match(rest):
                cur['items'].append({'cn': pending_cn or '', 'en': rest})
                pending_cn = None
            else:
                pending_cn = rest
            continue
        pair = split_cn_en(ln)
        if pair and pending_cn is None:
            cur['items'].append({'cn': pair[0], 'en': pair[1]})
        elif ASCII_RUN.match(ln):
            if pending_cn is not None:
                cur['items'].append({'cn': pending_cn, 'en': ln})
                pending_cn = None
            elif cur['items']:
                cur['items'][-1]['en'] += ' ' + ln
        else:
            pending_cn = (pending_cn + ' ' + ln) if pending_cn else ln
    groups = [g for g in groups if g['items']]
    return {'id': 'patterns', 'cat': '作文', 'title': '作文万能套用句型',
            'kind': 'pairs', 'src': '15.学位英语作文万能套用句型.pdf',
            'groups': groups}


# ---------------------------------------------------------------- 范文/模板

def parse_essay_real():
    """12.真题范文9篇：以 Directions / 首段命题为切点。"""
    t = tidy(read('12.学位英语作文范文（真题9篇）.txt'))
    t = re.sub(r'^学位英语作文真题范文\s*$', '', t, flags=re.M)
    # 切分点：Directions: 或 "You are to write"
    cuts = [m.start() for m in re.finditer(r'(?m)^(Directions:|You are to write)', t)]
    items = []
    for j, st in enumerate(cuts):
        en = cuts[j + 1] if j + 1 < len(cuts) else len(t)
        chunk = tidy(t[st:en])
        # 去掉中文点评尾巴
        chunk = re.split(r'(?m)^(?:作文参考|作文属于|【点评|点评：)', chunk)[0].strip()
        # 标题：命题里的 topic “X” 或 topic: X
        tm = re.search(r'topic[::]?\s*[“"]([^”"]+)', chunk)
        if not tm:
            tm = re.search(r'topic[::]?\s*([A-Za-z][^\n]{2,50})', chunk)
        title = f'真题范文 {j + 1}'
        if tm:
            title = re.split(r'You should|You are|要求|，|。', tm.group(1))[0]
            title = title.strip(' .，:"“”') or title
        items.append({'t': title, 'body': chunk})
    return {'id': 'essay-real', 'cat': '作文', 'title': '作文范文（真题9篇）',
            'kind': 'essays', 'src': '12.学位英语作文范文（真题9篇）.pdf', 'items': items}


SMALL = {'of', 'the', 'a', 'an', 'in', 'on', 'for', 'to', 'and', 'is', 'are',
         'my', 'our', 'your', 'his', 'her', 'its', 'at', 'by', 'with', 'how',
         'why', 'what', 'when', 'where', 'which', 'who'}


def guess_title(first_line: str) -> tuple[str, str]:
    """从「标题 + 正文首句」粘连行里猜标题：仅当正文以重复标题词开头时
    （如 …Habits Study habits play…）才有把握，否则返回空标题。"""
    tokens = first_line.split()
    norm = [t.lower().strip('“”"\'.,;:!?()') for t in tokens]
    for c in range(2, min(10, len(tokens) - 1)):
        for s in range(0, c):
            L = c - s
            if c + L <= len(tokens) and norm[c:c + L] == norm[s:s + L] \
                    and (c + L >= len(tokens) or norm[c + L].islower() or norm[c + L] in SMALL):
                return ' '.join(tokens[:c]).strip(' .,'), ' '.join(tokens[c:])
    return '', first_line


def parse_essay30():
    """13.通用30篇：按「成人学位英语考试作文 篇 N」切。"""
    t = tidy(read('13.学位英语作文范文（通用30篇）.txt'))
    t = re.sub(r'(?m)^\s*(?:51升学网)?程薇老师\s*$', '', t)
    pat = re.compile(r'^成人学位英语考试作文\s*篇\s*\d+\s*$')
    secs = split_by_headers(t, pat, keep_intro=False)
    items = []
    for idx, (head, body) in enumerate(secs, 1):
        lines = [x for x in body.split('\n') if x.strip()]
        title = f'范文 {idx}'
        if lines and re.match(r'^[A-Za-z]', lines[0]):
            t2, rest = guess_title(lines[0])
            if t2:
                title = t2
                lines[0] = rest
        items.append({'t': title, 'body': tidy('\n'.join(lines))})
    return {'id': 'essay30', 'cat': '作文', 'title': '作文范文（通用30篇）',
            'kind': 'essays', 'src': '13.学位英语作文范文（通用30篇）.pdf', 'items': items}


def parse_templates():
    """14.作文十大模板（OCR）：按「一、申请信」等切，去掉页眉。"""
    fp = EXT / '14.学位英语作文十大常见模板.ocr.txt'
    if not fp.exists():
        return None
    t = tidy(fp.read_text(encoding='utf-8'))
    t = re.sub(r'(?m)^2024学位英语万能模板$', '', t)
    t = re.sub(r'(?m)^（可直接套用）$', '', t)
    pat = re.compile(r'^[一二三四五六七八九十\d]{1,3}、[^\n]{1,25}$')
    secs = split_by_headers(t, pat)
    out = [(re.sub(r'^[一二三四五六七八九十\d]{1,3}、\s*', '', h), b) for h, b in secs]
    return article_mod('templates', '作文', '作文十大常见模板（应用文）',
                       '14.学位英语作文十大常见模板.pdf', out)


def parse_golden():
    """16.万能金句：按「写作类型X：…」切，保留【篇首句】等标记。"""
    t = tidy(strip_page_marks(read('16.学位英语作文常见题型万能金句.txt')))
    t = re.sub(r'^5\s*天背完[^\n]*$', '', t, flags=re.M)
    t = re.sub(r'^【英语作文万能句式[^\n]*】?$', '', t, flags=re.M)
    pat = re.compile(r'^[•·\s]*写作类型[一二三四五六七八九十]+[：:][^\n]{1,20}$')
    secs = split_by_headers(t, pat)
    out = [(re.sub(r'^写作类型[一二三四五六七八九十]+[：:]\s*', '', h), b) for h, b in secs]
    return article_mod('golden', '作文', '应用文万能金句（19类）',
                       '16.学位英语作文常见题型万能金句.pdf', out)


# ---------------------------------------------------------------- 主流程

def main():
    parsers = [
        parse_grammar_a, parse_grammar_b, parse_knowledge, parse_mcq_core,
        parse_colloc, parse_synonyms, parse_cloze_vocab, parse_cloze_phrases,
        parse_translate300,
        parse_essay_real, parse_essay30, parse_templates, parse_patterns, parse_golden,
    ]
    modules = []
    for p in parsers:
        try:
            m = p()
        except Exception as e:
            print(f'!! {p.__name__} 解析失败: {e}')
            continue
        if not m:
            continue
        if m['kind'] == 'article':
            n = len(m['sections'])
            size = sum(len(s['body']) for s in m['sections'])
        elif 'groups' in m:
            n = sum(len(g['items']) for g in m['groups'])
            size = n
        else:
            n = len(m['items'])
            size = n
        print(f"{m['id']:16s} {m['title']:24s} kind={m['kind']:8s} 条目/节={n} 量={size}")
        modules.append(m)
    json.dump({'modules': modules}, open(OUT, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'\n写出 {OUT}（{OUT.stat().st_size // 1024} KB）')


if __name__ == '__main__':
    main()
