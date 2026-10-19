#!/usr/bin/env python3
"""检索侧指标：召回、精度、排序。仅用标准库。

输入 JSONL，每行：
  {"id": "Q01", "type": "条款查询", "gold": ["制度A_v2024#3.2"], "retrieved": ["a", "b", ...]}
  - gold：标准出处标识；应拒答/库内无出处的题写 []，不计入召回与排序
  - retrieved：按排名从高到低；出处标识的粒度（文档/片段）全评测保持一致
  - type：可选，给了就按类型分别报告

指标（对有出处的题取宏平均）：
  hit@k        前 k 个里至少有一个标准出处的题占比
  recall@k     前 k 个里命中的标准出处数 / 标准出处总数
  precision@k  前 k 个里相关数 / 实际返回数（不足 k 个按返回数）
  MRR          第一个标准出处的排名倒数

脚本只计算用户给的标注，不判断标注是否正确，也不评价生成侧。
"""
import argparse
import json
import sys
from collections import defaultdict


def load(path):
    items = []
    with open(path, encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError("第 %d 行不是合法 JSON：%s" % (ln, e))
            for key in ("id", "gold", "retrieved"):
                if key not in d:
                    raise ValueError("第 %d 行缺少字段 %r" % (ln, key))
            if not isinstance(d["gold"], list) or not isinstance(d["retrieved"], list):
                raise ValueError("第 %d 行 gold 与 retrieved 必须是列表" % ln)
            items.append(d)
    return items


def per_item(d, ks):
    gold = set(d["gold"])
    ret = d["retrieved"]
    out = {}
    for k in ks:
        top = ret[:k]
        rel = [x for x in top if x in gold]
        out["hit@%d" % k] = 1.0 if rel else 0.0
        out["recall@%d" % k] = len(set(rel)) / len(gold)
        out["precision@%d" % k] = len(rel) / len(top) if top else 0.0
    rr = 0.0
    for i, x in enumerate(ret, 1):
        if x in gold:
            rr = 1.0 / i
            break
    out["MRR"] = rr
    return out


def mean(vals):
    return sum(vals) / len(vals)


def evaluate(items, ks):
    scored = [d for d in items if d["gold"]]
    refuse = [d for d in items if not d["gold"]]
    groups = defaultdict(list)
    rows = {}
    for d in scored:
        r = per_item(d, ks)
        rows[d["id"]] = r
        groups["全部"].append(r)
        if d.get("type"):
            groups[d["type"]].append(r)
    summary = {g: {m: mean([r[m] for r in rs]) for m in rs[0]} | {"n": len(rs)} for g, rs in groups.items()}
    kmax = max(ks)
    misses = [d["id"] for d in scored if rows[d["id"]]["hit@%d" % kmax] == 0.0]
    refuse_returned = [d["id"] for d in refuse if d["retrieved"]]
    return summary, misses, refuse, refuse_returned


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", required=True, help="标注记录 JSONL")
    p.add_argument("--k", default="3,5,10", help="逗号分隔的 k，默认 3,5,10")
    a = p.parse_args(argv)
    try:
        ks = sorted({int(x) for x in a.k.split(",")})
        if not ks or ks[0] < 1:
            raise ValueError
    except ValueError:
        sys.exit("--k 需要是正整数列表，如 3,5,10")
    try:
        items = load(a.input)
    except (OSError, ValueError) as e:
        sys.exit(str(e))
    if not items:
        sys.exit("没有记录")
    summary, misses, refuse, refuse_returned = evaluate(items, ks)
    if "全部" not in summary:
        sys.exit("所有题都没有标准出处，无法计算召回与排序")
    cols = ["hit@%d" % k for k in ks] + ["recall@%d" % k for k in ks] + ["precision@%d" % k for k in ks] + ["MRR"]
    print("\t".join(["类型", "n"] + cols))
    for g in sorted(summary, key=lambda x: (x != "全部", x)):
        s = summary[g]
        print("\t".join([g, str(s["n"])] + ["%.3f" % s[c] for c in cols]))
    print("\n前 %d 个里没有任何标准出处的题（回到“检索侧”四项）：%s" % (max(ks), "、".join(misses) or "无"))
    print("应拒答题（gold 为空）：%d 道；其中检索仍返回了材料的：%s" % (len(refuse), "、".join(refuse_returned) or "无"))
    print("拒答是否正确属生成侧，需另评。样本小时各类型的数值只用于发现失败机制，不外推。")


if __name__ == "__main__":
    main()
