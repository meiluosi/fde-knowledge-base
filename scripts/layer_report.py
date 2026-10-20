#!/usr/bin/env python3
"""四层任务的逐题标注汇总。仅用标准库。

四层见 references/task-layers.md：
  1 找到候选文件   2 核验版本/状态/适用范围   3 取得有权限的正文并定位   4 解释适用条件

输入 CSV 列：
  id        题目编号
  type      问题类型（可选，给了就分类型汇报）
  required  这道题要求达到的层级 1–4（由业务验收定）
  l1..l4    人工标注：1/是=通过，0/否=未通过，空=未评
  refusal   空=正常作答；safe=有依据的拒答；wrong=该答却拒答
  should_refuse  可选；1=这是应拒答题（库内无出处）。应拒答题不进“完成”的分母，
                 单独报“拒答正确”：有拒答（refusal 非空）算正确，正常作答算“不该答而答了”

规则：
  - 一道题达到的层级 = 从第 1 层起连续通过的层数；中间有未过或未评即停止。
  - 完成 = 达到的层级 >= required，且不是拒答。
  - 越层：后面的层标为通过而前面的层未过或未评，该题不按后面层计，单独列出。
  - 安全拒答（库内有出处但有依据地拒答）不计入完成，单列。
  - 应拒答题（should_refuse=1）单独汇总，不与完成率混在一个分母里。

脚本只汇总人工标注，不判断标注是否正确，也不评价答案本身。
"""
import argparse
import csv
import sys
from collections import Counter, defaultdict

from audit_sample import wilson

YES = {"1", "y", "yes", "true", "是", "通过", "t"}
NO = {"0", "n", "no", "false", "否", "未通过", "f"}


def parse_cell(v, qid, col):
    v = (v or "").strip().lower()
    if v == "":
        return None
    if v in YES:
        return True
    if v in NO:
        return False
    raise ValueError("题 %s 的 %s 列取值无法识别：%r" % (qid, col, v))


def evaluate_row(r):
    qid = r.get("id", "?")
    try:
        required = int((r.get("required") or "").strip())
    except ValueError:
        raise ValueError("题 %s 的 required 必须是 1–4 的整数" % qid)
    if not 1 <= required <= 4:
        raise ValueError("题 %s 的 required 必须是 1–4 的整数" % qid)
    layers = [parse_cell(r.get("l%d" % i), qid, "l%d" % i) for i in range(1, 5)]
    refusal = (r.get("refusal") or "").strip().lower()
    if refusal not in ("", "safe", "wrong"):
        raise ValueError("题 %s 的 refusal 只能是空、safe 或 wrong" % qid)
    should_refuse = parse_cell(r.get("should_refuse"), qid, "should_refuse") is True
    if should_refuse and refusal == "wrong":
        raise ValueError("题 %s 是应拒答题，refusal 不能是 wrong" % qid)

    achieved = 0
    for v in layers:
        if v is True:
            achieved += 1
        else:
            break
    skipped = any(v is True for v in layers[achieved + 1:]) if achieved < 4 else False
    unrated = [i + 1 for i in range(required) if layers[i] is None]
    first_fail = None
    for i in range(required):
        if layers[i] is False:
            first_fail = i + 1
            break
    complete = refusal == "" and achieved >= required
    return {
        "id": qid, "type": (r.get("type") or "").strip(), "required": required,
        "achieved": achieved, "complete": complete, "skipped": skipped,
        "unrated": unrated, "first_fail": first_fail, "refusal": refusal,
        "should_refuse": should_refuse,
    }


def summarize(rows):
    all_res = [evaluate_row(r) for r in rows]
    should = [x for x in all_res if x["should_refuse"]]
    res = [x for x in all_res if not x["should_refuse"]]
    answered = [x for x in res if x["refusal"] == ""]
    safe = [x["id"] for x in res if x["refusal"] == "safe"]
    wrong = [x["id"] for x in res if x["refusal"] == "wrong"]
    out = {
        "n": len(res),
        "should_refuse_n": len(should),
        "refused_correctly": sum(1 for x in should if x["refusal"] != ""),
        "answered_when_should_refuse": [x["id"] for x in should if x["refusal"] == ""],
        "answered": len(answered),
        "complete": sum(x["complete"] for x in res),
        "safe_refusal": safe,
        "wrong_refusal": wrong,
        "skipped": [x["id"] for x in res if x["skipped"]],
        "unrated": [(x["id"], x["unrated"]) for x in res if x["unrated"] and x["refusal"] == ""],
        "first_fail": Counter(x["first_fail"] for x in answered if x["first_fail"]),
        "by_type": defaultdict(lambda: [0, 0]),
        "achieved": Counter(x["achieved"] for x in answered),
    }
    for x in res:
        t = x["type"] or "（未分类）"
        out["by_type"][t][1] += 1
        out["by_type"][t][0] += x["complete"]
    return out


def fmt(k, n):
    lo, hi = wilson(k, n)
    return "%d/%d = %.1f%%，95%% 区间 %.1f%%–%.1f%%" % (k, n, 100 * k / n, 100 * lo, 100 * hi)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", required=True, help="逐题标注 CSV")
    a = p.parse_args(argv)
    try:
        with open(a.input, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            sys.exit("没有记录")
        s = summarize(rows)
    except (OSError, ValueError) as e:
        sys.exit(str(e))

    if s["n"]:
        print("完成（达到要求层级且正常作答；不含应拒答题）：" + fmt(s["complete"], s["n"]))
    else:
        print("没有应作答的题，无法计算完成率")
    print("  其中安全拒答 %d 道（不计入完成）、该答却拒答 %d 道、正常作答 %d 道" % (len(s["safe_refusal"]), len(s["wrong_refusal"]), s["answered"]))
    if s["should_refuse_n"]:
        print("应拒答题：%d 道，拒答正确 %s" % (s["should_refuse_n"], fmt(s["refused_correctly"], s["should_refuse_n"])))
        if s["answered_when_should_refuse"]:
            print("  不该答而答了：" + "、".join(s["answered_when_should_refuse"]))
    print("\n分类型：")
    for t in sorted(s["by_type"]):
        k, n = s["by_type"][t]
        print("  %s：%s" % (t, fmt(k, n)))
    print("\n正常作答题达到的层级分布：" + "，".join("第%d层=%d" % (k, s["achieved"][k]) for k in sorted(s["achieved"])) if s["achieved"] else "")
    print("首个未过的层（只看要求层级之内）：" + ("，".join("第%d层=%d" % (k, v) for k, v in sorted(s["first_fail"].items())) or "无"))
    if s["safe_refusal"]:
        print("安全拒答：" + "、".join(s["safe_refusal"]))
    if s["wrong_refusal"]:
        print("该答却拒答：" + "、".join(s["wrong_refusal"]))
    if s["skipped"]:
        print("越层标注（后面层通过而前面层未过或未评，已按连续通过计）：" + "、".join(s["skipped"]))
    if s["unrated"]:
        print("要求层级内尚有未评的层：" + "；".join("%s(第%s层)" % (i, "、".join(map(str, u))) for i, u in s["unrated"]))
    small = [t for t in s["by_type"] if s["by_type"][t][1] < 10]
    if small:
        print("注意：下列类型不足 10 题，区间很宽，只用于发现失败机制：" + "、".join(sorted(small)))
    print("完成率只汇总人工标注；评测集小或非代表性时不能外推。")


if __name__ == "__main__":
    main()
