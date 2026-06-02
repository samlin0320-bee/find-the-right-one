#!/usr/bin/env python3
"""貴人／小人／平宮分析器 — 兩人五格合盤判定。

姓名學雙人合盤的核心三條規則（出處：v72.html / 姓名學數位化第三堂課程逐字稿）：

  1. 貴人：A 的人格 == B 的地格 → A 是 B 的直接貴人
           reduce(A 人格) == reduce(B 地格) → A 是 B 的間接貴人（化氣，力量 10x）
  2. 小人：A 的總格 == B 的地格 → A 是 B 的明小人（拖累 B）
           reduce(A 總格) == reduce(B 地格) → A 是 B 的暗小人（化氣）
  3. 平宮：只看 人/地/總 三格（天/外 不看）
           人格相同 → 思維相近
           地格相同 → 感情/事業觀相近
           總格相同 → 人生目標一致

衍生：
  - 雙向互為貴人 → 合盤上吉
  - 雙向互為小人 → 合盤上凶
  - 雙向皆間接貴人 → 護貴人（課程：「兩條就超強」）
  - 一方五行俱全為貴人 → 100% 發揮貴人之力（加成）

用法：
    python3 guiren.py --a 李佳穎:9,16,24,17,32 --b 王大明:11,15,24,9,33
    python3 guiren.py --a 9,16,24,17,32 --b 11,15,24,9,33      # 不帶名字
    python3 guiren.py --a ... --b ... --json
    python3 guiren.py --assert                                  # 自驗

五格順序：天,人,地,外,總（其中只用 人/地/總；天/外 接收但忽略）
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from typing import Optional


# ==================== 化氣（reduce）====================

def reduce_digit(n: int) -> int:
    """姓名學官方化氣：拆位反覆相加直到 1-9。10→1, 15→6, 24→6, 25→7"""
    n = abs(int(n))
    while n > 9:
        n = sum(int(c) for c in str(n))
    return n


# ==================== 五行 / 俱全 ====================

# 個位數 → 五行（姓名學常見對照：1,2 木 / 3,4 火 / 5,6 土 / 7,8 金 / 9,0 水）
WUXING = {1: '木', 2: '木', 3: '火', 4: '火', 5: '土', 6: '土', 7: '金', 8: '金', 9: '水', 0: '水'}


def grid_wuxing(stroke: int) -> str:
    return WUXING[stroke % 10]


def is_wuxing_complete(strokes: list[int]) -> bool:
    """五格五行是否俱全（金木水火土皆有）。"""
    return len({grid_wuxing(s) for s in strokes}) == 5


# ==================== 資料結構 ====================

@dataclass
class Person:
    name: str
    tian: int
    ren: int
    di: int
    wai: int
    zong: int

    @property
    def strokes(self) -> list[int]:
        return [self.tian, self.ren, self.di, self.wai, self.zong]


@dataclass
class Relation:
    """單一條判定：A 對 B 的貴人／小人／平宮關係。"""
    kind: str            # 'noble' | 'villain' | 'equal'
    level: str           # 'direct' | 'indirect' | 'equal'
    direction: str       # 'A->B' | 'B->A' | 'both'
    grid_pair: str       # '人格→地格' / '總格→地格' / '人格=人格' ...
    a_value: int
    b_value: int
    huaqi: Optional[int] = None
    label: str = ''      # 中文標籤：直接貴人 / 間接貴人 / 明小人 / 暗小人 / 人格平宮 ...
    detail: str = ''


@dataclass
class Report:
    a: Person
    b: Person
    a_wuxing_complete: bool
    b_wuxing_complete: bool
    relations: list[Relation] = field(default_factory=list)
    flags: dict = field(default_factory=dict)     # mutual_noble / mutual_villain / huguiren ...
    verdict: str = ''                             # 整體一句話


# ==================== 核心判定 ====================

def _noble(a: Person, b: Person) -> list[Relation]:
    """A 對 B 的貴人線（人格→地格）。直接、間接獨立判定，可同時成立。"""
    out: list[Relation] = []
    # 直接：實數相同
    if a.ren == b.di:
        out.append(Relation(
            kind='noble', level='direct', direction='A->B',
            grid_pair='人格→地格', a_value=a.ren, b_value=b.di,
            label='直接貴人',
            detail=f'{a.name} 的人格({a.ren}) = {b.name} 的地格({b.di})，主動幫忙、直接給資源。',
        ))
    # 間接：化氣相同（且非直接才有意義；若同時相等則直接已涵蓋——但課程明示獨立列入）
    ha, hb = reduce_digit(a.ren), reduce_digit(b.di)
    if ha == hb:
        out.append(Relation(
            kind='noble', level='indirect', direction='A->B',
            grid_pair='人格→地格(化氣)', a_value=a.ren, b_value=b.di, huaqi=ha,
            label='間接貴人',
            detail=f'{a.name} 人格({a.ren})化氣{ha} = {b.name} 地格({b.di})化氣{hb}，'
                   f'介紹資源、力量約為直接的十倍。',
        ))
    return out


def _villain(a: Person, b: Person) -> list[Relation]:
    """A 對 B 的小人線（總格→地格）。A 的總格落在 B 的地格 → A 拖累 B。"""
    out: list[Relation] = []
    if a.zong == b.di:
        out.append(Relation(
            kind='villain', level='direct', direction='A->B',
            grid_pair='總格→地格', a_value=a.zong, b_value=b.di,
            label='明小人',
            detail=f'{a.name} 的總格({a.zong}) = {b.name} 的地格({b.di})，直接衝突、拖累 {b.name}。',
        ))
    ha, hb = reduce_digit(a.zong), reduce_digit(b.di)
    if ha == hb:
        out.append(Relation(
            kind='villain', level='indirect', direction='A->B',
            grid_pair='總格→地格(化氣)', a_value=a.zong, b_value=b.di, huaqi=ha,
            label='暗小人',
            detail=f'{a.name} 總格({a.zong})化氣{ha} = {b.name} 地格({b.di})化氣{hb}，'
                   f'無心之過、{b.name} 要幫 {a.name} 擦屁股。',
        ))
    return out


# 平宮：只看人/地/總三格；天/外不看
_EQUAL_GRIDS = [
    ('ren',  '人格平宮', '思維／個性相近'),
    ('di',   '地格平宮', '感情／事業觀相近'),
    ('zong', '總格平宮', '人生終極目標一致（最重要）'),
]


def _equals(a: Person, b: Person) -> list[Relation]:
    out: list[Relation] = []
    for attr, label, desc in _EQUAL_GRIDS:
        va, vb = getattr(a, attr), getattr(b, attr)
        if va == vb:
            cn = {'ren': '人格', 'di': '地格', 'zong': '總格'}[attr]
            out.append(Relation(
                kind='equal', level='equal', direction='both',
                grid_pair=f'{cn}={cn}', a_value=va, b_value=vb,
                label=label, detail=desc,
            ))
    return out


def analyze(a: Person, b: Person) -> Report:
    rels: list[Relation] = []
    rels.extend(_noble(a, b))
    rels.extend(_noble(b, a))
    # 第二次反向時改 direction 標籤
    # 重新跑一次更清楚
    rels = []
    rels.extend(_noble(a, b))                  # A->B 貴人
    for r in _noble(b, a):                     # B->A 貴人
        r.direction = 'B->A'
        r.detail = r.detail  # 已內含 b.name / a.name
        rels.append(r)
    rels.extend(_villain(a, b))                # A->B 小人 (A 拖累 B)
    for r in _villain(b, a):
        r.direction = 'B->A'
        rels.append(r)
    rels.extend(_equals(a, b))

    # 旗標
    has_ab_noble    = any(r.kind == 'noble'   and r.direction == 'A->B' for r in rels)
    has_ba_noble    = any(r.kind == 'noble'   and r.direction == 'B->A' for r in rels)
    has_ab_villain  = any(r.kind == 'villain' and r.direction == 'A->B' for r in rels)
    has_ba_villain  = any(r.kind == 'villain' and r.direction == 'B->A' for r in rels)
    has_ab_ind_noble = any(r.kind == 'noble' and r.level == 'indirect' and r.direction == 'A->B' for r in rels)
    has_ba_ind_noble = any(r.kind == 'noble' and r.level == 'indirect' and r.direction == 'B->A' for r in rels)

    flags = {
        'mutual_noble':   has_ab_noble   and has_ba_noble,    # 雙向互為貴人：合盤上吉
        'mutual_villain': has_ab_villain and has_ba_villain,  # 雙向互為小人：合盤上凶
        'huguiren':       has_ab_ind_noble and has_ba_ind_noble,  # 護貴人（兩條間接貴人）
        'a_to_b_noble':   has_ab_noble,
        'b_to_a_noble':   has_ba_noble,
        'a_to_b_villain': has_ab_villain,
        'b_to_a_villain': has_ba_villain,
    }

    a_wx = is_wuxing_complete(a.strokes)
    b_wx = is_wuxing_complete(b.strokes)

    verdict = _verdict(a, b, flags, a_wx, b_wx, rels)

    return Report(a=a, b=b,
                  a_wuxing_complete=a_wx, b_wuxing_complete=b_wx,
                  relations=rels, flags=flags, verdict=verdict)


def _labels_for(rels, direction: str, kind: str) -> list[str]:
    """收集指定方向 + 種類的所有 label（直接→間接 排序，去重保序）。"""
    order = {'direct': 0, 'indirect': 1, 'equal': 2}
    items = [r for r in rels if r.direction == direction and r.kind == kind]
    items.sort(key=lambda r: order.get(r.level, 9))
    seen, out = set(), []
    for r in items:
        if r.label not in seen:
            seen.add(r.label)
            out.append(r.label)
    return out


def _verdict(a, b, flags, a_wx, b_wx, rels) -> str:
    """整體一句話。優先順序：護貴人 > 合盤上吉/凶 > 雙重身份 > 單向。
    亦正亦邪時必須明確列出實際命中的標籤（直接貴人/間接貴人/明小人/暗小人），不能只說「貴人也是小人」。"""
    ab_n, ba_n = flags['a_to_b_noble'],   flags['b_to_a_noble']
    ab_v, ba_v = flags['a_to_b_villain'], flags['b_to_a_villain']

    if flags['huguiren']:
        return f'💖 護貴人：{a.name} 與 {b.name} 雙向皆為間接貴人，超強緣分。'
    if flags['mutual_noble'] and flags['mutual_villain']:
        return f'⚖️ 又貴又拖：兩人同時互為貴人與小人，緣分起伏大。'
    if flags['mutual_noble']:
        boost = '（雙方皆五行俱全，貴人之力 100% 發揮）' if (a_wx and b_wx) else ''
        return f'🌟 合盤上吉：{a.name} 與 {b.name} 雙向互為貴人{boost}。'
    if flags['mutual_villain']:
        return f'☠️ 合盤上凶：{a.name} 與 {b.name} 雙向互為小人，建議遠離。'

    def _dual(subj, obj, direction):
        nobles   = _labels_for(rels, direction, 'noble')    # 直接貴人 / 間接貴人
        villains = _labels_for(rels, direction, 'villain')  # 明小人 / 暗小人
        return (f'⚖️ {subj} 對 {obj} 亦正亦邪：'
                f'是 {obj} 的「{"、".join(nobles)}」，'
                f'同時也是 {obj} 的「{"、".join(villains)}」。')

    # 同一人對另一人「既貴又拖」的雙重身份
    if ab_n and ab_v and not (ba_n or ba_v):
        return _dual(a.name, b.name, 'A->B')
    if ba_n and ba_v and not (ab_n or ab_v):
        return _dual(b.name, a.name, 'B->A')

    # 單純單向貴人：把實際標籤（直接／間接）帶出來
    if ab_n and not (ba_n or ab_v or ba_v):
        labels = _labels_for(rels, 'A->B', 'noble')
        return f'👼 單向：{a.name} 是 {b.name} 的「{"、".join(labels)}」（{b.name} 受益較多）。'
    if ba_n and not (ab_n or ab_v or ba_v):
        labels = _labels_for(rels, 'B->A', 'noble')
        return f'👼 單向：{b.name} 是 {a.name} 的「{"、".join(labels)}」（{a.name} 受益較多）。'
    # 單純單向小人：把實際標籤（明／暗）帶出來
    if ab_v and not (ba_v or ab_n or ba_n):
        labels = _labels_for(rels, 'A->B', 'villain')
        return f'⚠️ 單向小人：{a.name} 是 {b.name} 的「{"、".join(labels)}」，會拖累 {b.name}。'
    if ba_v and not (ab_v or ab_n or ba_n):
        labels = _labels_for(rels, 'B->A', 'villain')
        return f'⚠️ 單向小人：{b.name} 是 {a.name} 的「{"、".join(labels)}」，會拖累 {a.name}。'

    # 其他混合（互貴+單向小人、互小人+單向貴人 …）：每方向把實際標籤條列出來
    parts = []
    for subj, obj, direction, has_n, has_v in [
        (a.name, b.name, 'A->B', ab_n, ab_v),
        (b.name, a.name, 'B->A', ba_n, ba_v),
    ]:
        labs = []
        if has_n: labs += _labels_for(rels, direction, 'noble')
        if has_v: labs += _labels_for(rels, direction, 'villain')
        if labs:
            parts.append(f'{subj}→{obj} 是「{"、".join(labs)}」')
    if parts:
        return f'🔀 混合關係：{"；".join(parts)}。'

    equals = [r.label for r in rels if r.kind == 'equal']
    if equals:
        return f'🤝 緣分平淡，但有 {"、".join(equals)}。'
    return '😐 緣分平淡：無明顯貴人、小人或平宮。'


# ==================== 文字輸出 ====================

def render_text(rep: Report) -> str:
    a, b = rep.a, rep.b
    lines = []
    lines.append(f'━━━ 貴人合盤：{a.name}  vs  {b.name} ━━━')
    lines.append(f'  {a.name} 五格 (天/人/地/外/總)：{a.tian}/{a.ren}/{a.di}/{a.wai}/{a.zong}'
                 f'   五行俱全：{"是" if rep.a_wuxing_complete else "否"}')
    lines.append(f'  {b.name} 五格 (天/人/地/外/總)：{b.tian}/{b.ren}/{b.di}/{b.wai}/{b.zong}'
                 f'   五行俱全：{"是" if rep.b_wuxing_complete else "否"}')
    lines.append('')

    def section(title, rels):
        if not rels:
            return
        lines.append(f'【{title}】')
        for r in rels:
            arrow = {'A->B': f'{a.name} → {b.name}',
                     'B->A': f'{b.name} → {a.name}',
                     'both': '雙向'}[r.direction]
            hq = f'(化氣 {r.huaqi})' if r.huaqi is not None else ''
            lines.append(f'  • [{arrow}] {r.label}{hq}：{r.grid_pair}  '
                         f'{r.a_value} ↔ {r.b_value}')
            lines.append(f'      {r.detail}')
        lines.append('')

    section('貴人線',   [r for r in rep.relations if r.kind == 'noble'])
    section('小人線',   [r for r in rep.relations if r.kind == 'villain'])
    section('平宮',     [r for r in rep.relations if r.kind == 'equal'])

    if rep.flags['huguiren']:
        lines.append('💖 護貴人觸發：雙向皆有間接貴人線。')
    if rep.flags['mutual_noble']:
        lines.append('🌟 雙向互為貴人（合盤上吉）。')
    if rep.flags['mutual_villain']:
        lines.append('☠️  雙向互為小人（合盤上凶）。')

    lines.append('')
    lines.append(f'結論：{rep.verdict}')
    return '\n'.join(lines)


# ==================== CLI 解析 ====================

def parse_person(spec: str, default_name: str) -> Person:
    """解析 '名字:9,16,24,17,32' 或 '9,16,24,17,32'。"""
    if ':' in spec:
        name, nums = spec.split(':', 1)
    else:
        name, nums = default_name, spec
    parts = [int(x.strip()) for x in nums.split(',')]
    if len(parts) != 5:
        raise ValueError(f'需要 5 個筆劃 (天,人,地,外,總)，收到 {len(parts)} 個：{spec}')
    if any(p < 1 for p in parts):
        raise ValueError(f'筆劃需 ≥1：{spec}')
    return Person(name=name or default_name,
                  tian=parts[0], ren=parts[1], di=parts[2], wai=parts[3], zong=parts[4])


def report_to_dict(rep: Report) -> dict:
    return {
        'a': asdict(rep.a), 'b': asdict(rep.b),
        'a_wuxing_complete': rep.a_wuxing_complete,
        'b_wuxing_complete': rep.b_wuxing_complete,
        'relations': [asdict(r) for r in rep.relations],
        'flags': rep.flags,
        'verdict': rep.verdict,
    }


# ==================== 自驗 ====================

def _assert():
    # 化氣
    assert reduce_digit(10) == 1
    assert reduce_digit(15) == 6
    assert reduce_digit(24) == 6
    assert reduce_digit(25) == 7
    assert reduce_digit(99) == 9   # 9+9=18 → 1+8=9

    # 構造一個 A 是 B 直接貴人的例子：A.人 == B.地
    A = Person('甲', tian=10, ren=24, di=20, wai=11, zong=34)
    B = Person('乙', tian=11, ren=15, di=24, wai=10, zong=39)  # B.地=24=A.人
    rep = analyze(A, B)
    ab = [r for r in rep.relations if r.direction == 'A->B' and r.kind == 'noble']
    assert any(r.level == 'direct' for r in ab), '應有直接貴人 A->B'
    # A.人=24 化氣 6；B.地=24 化氣 6 → 也構成間接（兩條獨立列）
    assert any(r.level == 'indirect' for r in ab), '同數時間接亦列入'

    # 間接但非直接：A.人=15 (化氣6) vs B.地=24 (化氣6)
    A2 = Person('丙', tian=10, ren=15, di=10, wai=11, zong=30)
    B2 = Person('丁', tian=11, ren=10, di=24, wai=10, zong=20)
    rep2 = analyze(A2, B2)
    ab2 = [r for r in rep2.relations if r.direction == 'A->B' and r.kind == 'noble']
    assert all(r.level != 'direct' for r in ab2), '不應有直接貴人 A->B'
    assert any(r.level == 'indirect' for r in ab2), '應有間接貴人 A->B'

    # 小人：A.總 == B.地
    A3 = Person('戊', tian=10, ren=10, di=10, wai=10, zong=24)
    B3 = Person('己', tian=10, ren=10, di=24, wai=10, zong=10)
    rep3 = analyze(A3, B3)
    assert any(r.kind == 'villain' and r.direction == 'A->B' and r.level == 'direct'
               for r in rep3.relations), '應有 A 對 B 明小人'

    # 護貴人：雙向皆間接貴人
    # A.人 化氣 == B.地 化氣 + B.人 化氣 == A.地 化氣
    # 取 A.人=15(化6), A.地=23(化5)；B.人=14(化5), B.地=24(化6)
    A4 = Person('庚', tian=10, ren=15, di=23, wai=10, zong=30)
    B4 = Person('辛', tian=10, ren=14, di=24, wai=10, zong=30)
    rep4 = analyze(A4, B4)
    assert rep4.flags['huguiren'], '應觸發護貴人'

    # 平宮（地格）+ 雙向互為貴人
    A5 = Person('壬', tian=10, ren=24, di=20, wai=10, zong=30)
    B5 = Person('癸', tian=10, ren=20, di=24, wai=10, zong=30)
    rep5 = analyze(A5, B5)
    assert rep5.flags['mutual_noble'], 'A 人=24=B 地, B 人=20=A 地 → 互為直接貴人'
    assert any(r.label == '總格平宮' for r in rep5.relations), '總格 30=30 → 平宮'

    # 亦正亦邪：verdict 必須明確點出「直接貴人 + 暗小人」之類的具體標籤
    # 設計：B 對 A 是 間接貴人（B.人=15 化6 = A.地=24 化6）
    #       B 對 A 也是 暗小人 （B.總=33 化6 = A.地=24 化6）
    A6 = Person('李', tian=9, ren=16, di=24, wai=17, zong=32)
    B6 = Person('王', tian=11, ren=15, di=24, wai=9, zong=33)
    rep6 = analyze(A6, B6)
    assert '亦正亦邪' in rep6.verdict, '應觸發亦正亦邪'
    assert '間接貴人' in rep6.verdict, 'verdict 必須點出「間接貴人」'
    assert '暗小人' in rep6.verdict, 'verdict 必須點出「暗小人」'

    # 亦正亦邪：直接貴人 + 明小人 的具體標籤
    # A.人 = B.地（直接貴人 A→B）
    # A.總 = B.地（明小人 A→B）→ 需要 A.人 == A.總 == B.地
    A7 = Person('甲', tian=10, ren=24, di=10, wai=10, zong=24)
    B7 = Person('乙', tian=10, ren=11, di=24, wai=10, zong=11)
    rep7 = analyze(A7, B7)
    assert '亦正亦邪' in rep7.verdict, '應觸發亦正亦邪（A→B）'
    assert '直接貴人' in rep7.verdict, 'verdict 必須點出「直接貴人」'
    assert '明小人' in rep7.verdict, 'verdict 必須點出「明小人」'

    # 單向貴人 verdict 也要帶出標籤（直接 / 間接）
    A8 = Person('丙', tian=10, ren=24, di=10, wai=10, zong=11)
    B8 = Person('丁', tian=10, ren=11, di=24, wai=10, zong=20)
    rep8 = analyze(A8, B8)
    assert '直接貴人' in rep8.verdict, '單向 verdict 也要點出「直接貴人」'

    # 單向小人 verdict 要帶「明小人」/「暗小人」
    A9 = Person('戊', tian=10, ren=10, di=10, wai=10, zong=24)
    B9 = Person('己', tian=10, ren=11, di=24, wai=10, zong=11)
    rep9 = analyze(A9, B9)
    assert '明小人' in rep9.verdict, '單向 verdict 要點出「明小人」'

    print('✓ 全部斷言通過')


# ==================== main ====================

def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description='貴人／小人／平宮分析器（兩人合盤）')
    p.add_argument('--a', help='A 方：「名字:天,人,地,外,總」 或 「天,人,地,外,總」')
    p.add_argument('--b', help='B 方：「名字:天,人,地,外,總」 或 「天,人,地,外,總」')
    p.add_argument('--json', action='store_true', help='輸出 JSON')
    p.add_argument('--assert', dest='do_assert', action='store_true', help='跑內建斷言')
    args = p.parse_args(argv)

    if args.do_assert:
        _assert()
        return 0

    if not args.a or not args.b:
        p.error('需要 --a 與 --b（或 --assert）')

    a = parse_person(args.a, default_name='A')
    b = parse_person(args.b, default_name='B')
    rep = analyze(a, b)

    if args.json:
        print(json.dumps(report_to_dict(rep), ensure_ascii=False, indent=2))
    else:
        print(render_text(rep))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
