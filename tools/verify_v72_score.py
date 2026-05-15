#!/usr/bin/env python3
"""
v72.html calculateAffinityScore 的 Python 對照實作。

用途：離線批次驗證／搜尋符合條件的公司名（或對應字組合）。
邏輯與 v72.html 第 704–812 行的 JavaScript 計分函式一致。

使用方式：
    python3 tools/verify_v72_score.py

輸出：對「李佳穎」兩版本筆劃，找出 100 分的 3-字單姓公司名範例，
      列出五格、五行、陰陽盤、計分明細。
"""
from __future__ import annotations
import json
import sys
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / 'kangxi_db.json'


def load_db() -> dict[str, int]:
    return json.loads(DB_PATH.read_text())


def get_wuxing(num: int) -> str:
    tail = num % 10
    if tail in (1, 2): return '木'
    if tail in (3, 4): return '火'
    if tail in (5, 6): return '土'
    if tail in (7, 8): return '金'
    return '水'  # tail 0 or 9


def check_wuxing_complete(grids: list[int]) -> bool:
    return len({get_wuxing(g) for g in grids}) == 5


def reduce_num(n: int) -> int:
    while n > 9:
        n = sum(int(d) for d in str(n))
    return n


def analyze_polarity(grids: list[int]) -> str:
    odd = sum(1 for g in grids if g % 2)
    even = 5 - odd
    if odd == 5: return '全陽盤'
    if even == 5: return '全陰盤'
    if odd >= 4: return '偏陽盤'
    if even >= 4: return '偏陰盤'
    return '陰陽平衡'


def five_grids_3char(s1: int, s2: int, s3: int) -> dict[str, int]:
    """三字單姓的五格計算（v72.html 第 501-503 行）"""
    tian = s1 + 1
    ren = s1 + s2
    di = s2 + s3
    zong = s1 + s2 + s3
    wai = zong - ren + 1
    return dict(tian=tian, ren=ren, di=di, wai=wai, zong=zong)


def calc_score(A: dict, B: dict, pol_a: str, pol_b: str) -> tuple[int, int, list[str]]:
    """忠實複製 v72.html calculateAffinityScore"""
    score = 40
    lines: list[str] = []

    a_complete = check_wuxing_complete([A[k] for k in ('tian', 'ren', 'di', 'wai', 'zong')])
    b_complete = check_wuxing_complete([B[k] for k in ('tian', 'ren', 'di', 'wai', 'zong')])

    a_dir_noble = A['ren'] == B['di']
    a_ind_noble = reduce_num(A['ren']) == reduce_num(B['di'])
    b_dir_noble = B['ren'] == A['di']
    b_ind_noble = reduce_num(B['ren']) == reduce_num(A['di'])
    a_dir_vill = A['zong'] == B['di']
    a_ind_vill = reduce_num(A['zong']) == reduce_num(B['di'])
    b_dir_vill = B['zong'] == A['di']
    b_ind_vill = reduce_num(B['zong']) == reduce_num(A['di'])

    def add_noble(is_a_to_b: bool, is_indirect: bool):
        nonlocal score
        base = 12 if is_indirect else 20
        wb = (is_a_to_b and a_complete) or ((not is_a_to_b) and b_complete)
        pts = base + (5 if wb else 0)
        score += pts
        tag = '間接貴人' if is_indirect else '直接貴人'
        note = '・五行俱全加成' if wb else ''
        subj, obj = ('A', 'B') if is_a_to_b else ('B', 'A')
        lines.append(f'{subj}→{obj} {tag}{note} +{pts}')

    def add_villain(is_a_to_b: bool, is_indirect: bool):
        nonlocal score
        pts = 8 if is_indirect else 15
        score -= pts
        tag = '暗小人' if is_indirect else '明小人'
        subj, obj = ('A', 'B') if is_a_to_b else ('B', 'A')
        lines.append(f'{subj}→{obj} {tag} -{pts}')

    if a_dir_noble: add_noble(True, False)
    elif a_ind_noble: add_noble(True, True)
    if b_dir_noble: add_noble(False, False)
    elif b_ind_noble: add_noble(False, True)
    if a_dir_vill: add_villain(True, False)
    elif a_ind_vill: add_villain(True, True)
    if b_dir_vill: add_villain(False, False)
    elif b_ind_vill: add_villain(False, True)

    a_is_noble = a_dir_noble or a_ind_noble
    b_is_noble = b_dir_noble or b_ind_noble
    a_is_vill = a_dir_vill or a_ind_vill
    b_is_vill = b_dir_vill or b_ind_vill
    if a_is_noble and b_is_noble:
        score += 6; lines.append('雙向互為貴人 +6')
    if a_is_vill and b_is_vill:
        score -= 6; lines.append('雙向互為小人 -6')
    if a_ind_noble and b_ind_noble and not a_dir_noble and not b_dir_noble:
        score += 8; lines.append('護貴人 +8')

    if A['ren'] == B['ren']:
        score += 6; lines.append('人格平宮 +6')
    if A['di'] == B['di']:
        score += 6; lines.append('地格平宮 +6')
    if A['zong'] == B['zong']:
        score += 8; lines.append('總格平宮 +8')

    if a_complete and b_complete:
        score += 4; lines.append('雙方五行俱全 +4')

    if (pol_a == '全陽盤' and pol_b == '全陰盤') or (pol_a == '全陰盤' and pol_b == '全陽盤'):
        score -= 2; lines.append('陰陽極端對立 -2')

    raw = score
    capped = max(1, min(100, round(score)))
    return capped, raw, lines


# ============================================================
# 範例：對「李佳穎」兩版本，找 100 分公司名（3 字單姓）
# ============================================================

# Version A：李=8, 佳=8, 穎=16 → 天9 人16 地24 外17 總32
VERSION_A = dict(name='李佳穎-A', tian=9, ren=16, di=24, wai=17, zong=32)
# Version B：李=6, 佳=8, 穎=18 → 天7 人14 地26 外19 總32
VERSION_B = dict(name='李佳穎-B', tian=7, ren=14, di=26, wai=19, zong=32)


def render(parts: tuple[str, str, str], target: dict, target_pol: str, db: dict) -> int:
    s = [db[c] for c in parts]
    g = five_grids_3char(*s)
    name = ''.join(parts)
    b = dict(name=name, **g)
    pol_b = analyze_polarity([b[k] for k in ('tian', 'ren', 'di', 'wai', 'zong')])
    score, raw, lines = calc_score(target, b, target_pol, pol_b)
    complete = check_wuxing_complete([g[k] for k in ('tian', 'ren', 'di', 'wai', 'zong')])

    print(f'\n  公司：{name}')
    print(f'    筆劃：{parts[0]}={s[0]}  {parts[1]}={s[1]}  {parts[2]}={s[2]}')
    print(f'    五格：天{g["tian"]:>2}({get_wuxing(g["tian"])}) '
          f'人{g["ren"]:>2}({get_wuxing(g["ren"])}) '
          f'地{g["di"]:>2}({get_wuxing(g["di"])}) '
          f'外{g["wai"]:>2}({get_wuxing(g["wai"])}) '
          f'總{g["zong"]:>2}({get_wuxing(g["zong"])})')
    print(f'    陰陽：{pol_b}    五行俱全：{"✓" if complete else "✗"}')
    print(f'    計分（base 40）：')
    for line in lines:
        print(f'      • {line}')
    print(f'    raw={raw} → cap → {score} 分  {"✅" if score == 100 else "❌"}')
    return score


def main() -> int:
    db = load_db()
    pol_a = analyze_polarity([VERSION_A[k] for k in ('tian', 'ren', 'di', 'wai', 'zong')])
    pol_b = analyze_polarity([VERSION_B[k] for k in ('tian', 'ren', 'di', 'wai', 'zong')])

    picks_a = [('學', '沛', '和'), ('錦', '東', '昕'), ('璇', '宜', '青')]
    picks_b = [('鎮', '和', '宇'), ('蕭', '青', '旭'), ('豐', '昕', '吉')]

    print('=' * 60)
    print('Version A — 對手「李佳穎」筆劃 8/8/16')
    print(f'  五格：天9(水) 人16(土) 地24(火) 外17(金) 總32(木)  {pol_a}')
    print('  公司結構：16-8-8 三字單姓')
    print('=' * 60)
    all_ok = True
    for p in picks_a:
        if render(p, VERSION_A, pol_a, db) != 100:
            all_ok = False

    print('\n' + '=' * 60)
    print('Version B — 對手「李佳穎」筆劃 6/8/18')
    print(f'  五格：天7(金) 人14(火) 地26(土) 外19(水) 總32(木)  {pol_b}')
    print('  公司結構：18-8-6 三字單姓')
    print('=' * 60)
    for p in picks_b:
        if render(p, VERSION_B, pol_b, db) != 100:
            all_ok = False

    print('\n' + '=' * 60)
    print(f'結果：{"全 6 組達 100 分 ✅" if all_ok else "有未達 100 ❌"}')
    print('=' * 60)
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
