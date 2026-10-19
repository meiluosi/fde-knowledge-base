#!/usr/bin/env python3
"""文档摸底的抽样与通过率区间。仅用标准库。

脚本只对用户提供的清单与判定结果做算术，不验证清单是否完整、判定是否正确。

  sample  从文件清单 CSV 中按层抽样（可复现）
  rate    由通过/总数或逐份判定 CSV 计算通过率及 Wilson 95% 区间
"""
import argparse
import csv
import math
import random
import sys
from collections import defaultdict

Z95 = 1.959963984540054


def wilson(k, n, z=Z95):
    if n <= 0:
        raise ValueError("总数必须大于 0")
    if not 0 <= k <= n:
        raise ValueError("通过数必须在 0 到总数之间")
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def allocate(sizes, n):
    """按层大小比例分配 n，最大余数法；每层至少 1 份。"""
    strata = sorted(sizes)
    total = sum(sizes.values())
    if n > total:
        raise ValueError("n 大于清单总数 %d" % total)
    if n < len(strata):
        raise ValueError("n=%d 小于层数 %d，无法每层至少抽 1 份" % (n, len(strata)))
    quotas = {s: max(1, int(n * sizes[s] / total)) for s in strata}
    quotas = {s: min(q, sizes[s]) for s, q in quotas.items()}
    # 先把超额的拿回来，再按余数补足
    while sum(quotas.values()) > n:
        s = max((x for x in strata if quotas[x] > 1), key=lambda x: quotas[x])
        quotas[s] -= 1
    rema = sorted(strata, key=lambda s: (-(n * sizes[s] / total - int(n * sizes[s] / total)), s))
    i = 0
    while sum(quotas.values()) < n:
        s = rema[i % len(rema)]
        if quotas[s] < sizes[s]:
            quotas[s] += 1
        i += 1
        if i > 10 * len(rema) + n:
            break
    return quotas


def draw(rows, strata_col, n, seed):
    groups = defaultdict(list)
    for r in rows:
        groups[r[strata_col]].append(r)
    quotas = allocate({s: len(v) for s, v in groups.items()}, n)
    rng = random.Random(seed)
    picked = []
    for s in sorted(groups):
        members = sorted(groups[s], key=lambda r: tuple(r.values()))
        picked.extend(rng.sample(members, quotas[s]))
    return picked, quotas


def cmd_sample(a):
    with open(a.manifest, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = reader.fieldnames
    if not rows:
        sys.exit("清单为空")
    if a.strata_col not in fields:
        sys.exit("清单里没有分层列 %r，可用列：%s" % (a.strata_col, ", ".join(fields)))
    try:
        picked, quotas = draw(rows, a.strata_col, a.n, a.seed)
    except ValueError as e:
        sys.exit(str(e))
    out = open(a.out, "w", newline="", encoding="utf-8") if a.out else sys.stdout
    w = csv.DictWriter(out, fieldnames=fields)
    w.writeheader()
    w.writerows(picked)
    if a.out:
        out.close()
    print("抽样 %d 份，种子 %s；各层：%s" % (len(picked), a.seed, ", ".join("%s=%d" % kv for kv in sorted(quotas.items()))), file=sys.stderr)
    print("提醒：抽样框是否完整、是否随机，由使用者负责记录；客户自选样例不是随机样本。", file=sys.stderr)


def fmt(k, n):
    lo, hi = wilson(k, n)
    return "%d/%d = %.1f%%，95%% 区间 %.1f%%–%.1f%%" % (k, n, 100 * k / n, 100 * lo, 100 * hi)


def cmd_rate(a):
    if a.results:
        with open(a.results, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            sys.exit("结果为空")
        for col in (a.pass_col, a.strata_col):
            if col not in rows[0]:
                sys.exit("结果里没有列 %r" % col)
        yes = {"1", "y", "yes", "true", "是", "通过", "t"}
        no = {"0", "n", "no", "false", "否", "未通过", "f"}
        by = defaultdict(lambda: [0, 0])
        for r in rows:
            v = r[a.pass_col].strip().lower()
            if v not in yes and v not in no:
                sys.exit("无法识别的通过值 %r（文档 %s）" % (r[a.pass_col], r.get("id", "?")))
            by[r[a.strata_col]][1] += 1
            by[r[a.strata_col]][0] += v in yes
        K = sum(v[0] for v in by.values())
        N = sum(v[1] for v in by.values())
        print("总体：" + fmt(K, N))
        for s in sorted(by):
            print("  %s：%s" % (s, fmt(*by[s])))
        small = [s for s in by if by[s][1] < 10]
        if small:
            print("注意：下列层样本不足 10 份，区间很宽，只用于发现失败机制：" + "、".join(sorted(small)))
    else:
        if a.pass_ is None or a.total is None:
            sys.exit("需要 --results，或同时给 --pass 与 --total")
        try:
            print(fmt(a.pass_, a.total))
        except ValueError as e:
            sys.exit(str(e))
    print("区间只反映抽样误差；样本非随机或抽样框不全时，不能外推到总体。")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample", help="按层抽样")
    s.add_argument("--manifest", required=True, help="文件清单 CSV（含表头）")
    s.add_argument("--strata-col", required=True, help="分层列名")
    s.add_argument("--n", type=int, default=50, help="总抽样数（书稿经验起点 50，非统计保证）")
    s.add_argument("--seed", type=int, required=True, help="随机种子，须记录")
    s.add_argument("--out", help="输出 CSV，缺省写到标准输出")
    s.set_defaults(fn=cmd_sample)
    r = sub.add_parser("rate", help="通过率及 Wilson 区间")
    r.add_argument("--results", help="逐份判定 CSV")
    r.add_argument("--pass-col", default="pass")
    r.add_argument("--strata-col", default="stratum")
    r.add_argument("--pass", dest="pass_", type=int)
    r.add_argument("--total", type=int)
    r.set_defaults(fn=cmd_rate)
    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
