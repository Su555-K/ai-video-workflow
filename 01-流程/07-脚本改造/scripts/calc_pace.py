#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
语速时长核算 —— 配合 语速时长核算表.md 使用

用法：
    python3 calc_pace.py 脚本.txt --pace 5.5
    python3 calc_pace.py 脚本.txt --pace 5.5 --total 20

输入格式（每镜一行，竖线分隔）：
    01|2.0|看这个M级和牛
    02|1.5|下锅涮5秒

算法：
    需要时间 = 音节数 / 语速 * 1.1(口语冗余) + 停顿
    差 = 排的时长 - 需要时间
"""
import argparse
import re
import sys

# 标点停顿时长（秒）
PAUSE = {
    '，': 0.25, ',': 0.25,
    '、': 0.20,
    '。': 0.45, '？': 0.45, '?': 0.45,
    '！': 0.40, '!': 0.40,
    '…': 0.60,
}

CN_DIGIT = '零一二三四五六七八九'


def num_syllables(numstr: str) -> int:
    """阿拉伯数字转成中文读法的音节数。138 -> 一百三十八 -> 5"""
    n = int(numstr)
    if n < 10:
        return 1
    if n == 10:
        return 1                      # 十
    if n < 20:
        return 2                      # 十五
    if n < 100:
        tens, ones = divmod(n, 10)
        return 2 + (1 if ones else 0)  # 二十三 -> 二十(2)+三(1)
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        s = 2 if hundreds == 1 else 2  # 一百 / 二百 都是 2 音节
        if rest == 0:
            return s
        if rest < 10:
            return s + 2              # 一百零五
        tens, ones = divmod(rest, 10)
        s += 1 if tens == 1 else 2     # 十 / 三十
        if ones:
            s += 1
        return s
    if n < 10000:
        thousands, rest = divmod(n, 1000)
        s = 2                          # 一千
        if rest == 0:
            return s
        if rest < 100:
            return s + (pinyin_small(rest) + 1)  # 一千零五十
        return s + num_syllables(str(rest))
    return len(str(n))


def pinyin_small(n: int) -> int:
    """0-99 音节数（内部用，粗略）"""
    if n < 10:
        return 1
    tens, ones = divmod(n, 10)
    return (1 if tens == 1 else 2) + (1 if ones else 0)


def eng_syllables(word: str) -> int:
    """英文按元音组数估音节。New -> 1, Video -> 3, M -> 1"""
    w = word.lower()
    groups = re.findall(r'[aeiouy]+', w)
    n = len(groups)
    if w.endswith('e') and n > 1 and not w.endswith(('le', 'ee')):
        n -= 1
    return max(1, n)


def count_syllables(text: str):
    """返回 (音节数, 停顿总秒, 明细)"""
    syl = 0
    pause = 0.0
    detail = []

    # 先拆数字（含小数不处理，简化）
    tokens = re.findall(r'\d+|[A-Za-z]+|[\u4e00-\u9fff]|[，,、。？?！!…]', text)

    for t in tokens:
        if t.isdigit():
            k = num_syllables(t)
            syl += k
            detail.append(f'{t}={k}')
        elif re.match(r'[A-Za-z]', t):
            k = eng_syllables(t)
            syl += k
            detail.append(f'{t}={k}')
        elif t in PAUSE:
            pause += PAUSE[t]
        else:
            syl += 1

    return syl, pause, detail


def judge(diff: float, kind: str = 'auto') -> str:
    if kind in ('D', 'C', 'E'):      # 空镜/动作/留白：富余不算注水
        if diff < -1.2:
            return '🔴 念不完'
        if diff < -0.5:
            return '🟡 偏紧'
        return '✅ 画面驱动'
    if diff < -1.2:
        return '🔴 念不完'
    if diff < -0.5:
        return '🟡 偏紧'
    if diff <= 0.5:
        return '✅ 合适'
    if diff <= 1.0:
        return '🟢 宽松'
    return '🔵 富余'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('file')
    ap.add_argument('--pace', type=float, default=5.5,
                    help='语速 字/秒：平静4.0 常规4.5 探店5.5-6.0 情绪3.5')
    ap.add_argument('--total', type=float, default=None, help='全片时长，用于底线校验')
    ap.add_argument('--kinds', default=None,
                    help='镜头类型串，如 A,B,D,D —— 对应每镜，D/C/E 富余不算注水')
    args = ap.parse_args()

    rows = []
    with open(args.file, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split('|')
            if len(parts) < 3:
                continue
            no, dur, text = parts[0].strip(), float(parts[1]), parts[2].strip()
            rows.append((no, dur, text))

    if not rows:
        print('没读到数据，格式应为：镜号|时长|口播')
        sys.exit(1)

    kinds = args.kinds.split(',') if args.kinds else ['auto'] * len(rows)

    print(f'语速基准：{args.pace} 字/秒 ｜ 口语冗余 ×1.1')
    print('=' * 88)
    print(f"{'镜号':<4}{'排的':>6}{'音节':>5}{'停顿':>6}{'需要':>7}{'差':>7}  判定")
    print('-' * 88)

    total_syl = 0
    total_pause = 0.0
    total_dur = 0.0
    total_need = 0.0

    for (no, dur, text), kind in zip(rows, kinds):
        syl, pause, _ = count_syllables(text)
        need = syl / args.pace * 1.1 + pause
        diff = dur - need
        total_syl += syl
        total_pause += pause
        total_dur += dur
        total_need += need
        print(f'{no:<4}{dur:>6.1f}{syl:>5}{pause:>6.2f}{need:>7.2f}{diff:>+7.2f}  {judge(diff, kind)}')

    print('-' * 88)
    print(f'合计 {total_dur:.1f}s ｜ 音节 {total_syl} ｜ 需要 {total_need:.2f}s ｜ 差 {total_dur-total_need:+.2f}s')
    print(f'全片实际语速 {total_syl/total_dur:.2f} 音节/秒（按音节计，与 {args.pace} 字/秒的基准不是同一口径，仅作参考）')

    total = args.total or total_dur
    limit = total * 0.9
    print(f'底线：台词需 ≤ 全片×0.9 = {limit:.1f}s ｜ 实际需要 {total_need:.1f}s ｜ '
          f'{"✅ 过" if total_need <= limit else "❌ 超"}')
    print()
    print('提示：差 < -1.2 是念不完。复刻场景先回去核对原片这一镜真实时长。')


if __name__ == '__main__':
    main()
