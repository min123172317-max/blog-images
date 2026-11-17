#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""실제 조회수 순위표(data/views_monthly.tsv)와 댓글 수(data/blog_stats.tsv)를 글별로 맞춰 비교한다.
실행: python3 tools/views_compare.py
"""
import csv, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "..", "data")
norm = lambda s: re.sub(r"[^0-9A-Za-z가-힣]", "", s)

posts = list(csv.DictReader(open(os.path.join(D, "blog_stats.tsv"), encoding="utf-8"), delimiter="\t"))
for p in posts:
    p["n"] = norm(p["title"]); p["views"] = {}; p["comments"] = int(p["comments"] or 0)
views = list(csv.DictReader(open(os.path.join(D, "views_monthly.tsv"), encoding="utf-8"), delimiter="\t"))
miss = []
for v in views:
    pre = norm(v["title_prefix"])
    c = [p for p in posts if p["date"] == v["date"] and p["n"].startswith(pre[:6])]
    if len(c) != 1:
        c = [p for p in posts if p["date"] == v["date"] and pre[:4] in p["n"]]
    if len(c) == 1:
        c[0]["views"][v["month"]] = int(v["views"])
    else:
        miss.append((v["month"], v["rank"], v["date"], v["title_prefix"], len(c)))
print("조회수 행 %d개 중 글과 맞춘 것 %d개, 못 맞춘 것 %d개" % (len(views), len(views) - len(miss), len(miss)))
for m in miss[:12]: print("  못 맞춤:", m)

def rank(xs):
    o = sorted(range(len(xs)), key=lambda i: xs[i]); r = [0.0] * len(xs); i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and xs[o[j + 1]] == xs[o[i]]: j += 1
        for k in range(i, j + 1): r[o[k]] = (i + j) / 2 + 1
        i = j + 1
    return r
def spearman(a, b):
    ra, rb = rank(a), rank(b); n = len(a); ma = sum(ra) / n; mb = sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** .5
    return num / den if den else 0

# 8~10월 사이에 올라온 글만 (조회수 표에 없으면 해당 월 순위권 밖 = 0으로 둠)
S = [p for p in posts if "2026-08-01" <= p["date"] <= "2026-10-31"]
tot = [sum(p["views"].values()) for p in S]; cm = [p["comments"] for p in S]
print("\n대상 글 %d편 (8/1~10/31 발행), 조회수 순위권(1~60위 안팎)에 든 글 %d편" % (len(S), sum(1 for t in tot if t)))
print("순위 상관(스피어만): 댓글 vs 조회수 = %.2f" % spearman(cm, tot))
inl = [(c, t) for c, t in zip(cm, tot) if t]
print("순위권 안의 글끼리만: %.2f (글 %d편)" % (spearman([c for c, _ in inl], [t for _, t in inl]), len(inl)))

by = sorted(S, key=lambda p: -sum(p["views"].values()))
top = by[:30]; topc = sorted(S, key=lambda p: -p["comments"])[:30]
print("조회수 상위 30편 중 댓글 상위 30편에도 든 글: %d편" % len(set(id(p) for p in top) & set(id(p) for p in topc)))
print("댓글 10개 이상 글 %d편 중 조회수 순위권 글: %d편" % (sum(1 for p in S if p["comments"] >= 10), sum(1 for p in S if p["comments"] >= 10 and p["views"])))
g = {}
for p in S:
    b = "0~1" if p["comments"] <= 1 else "2~4" if p["comments"] <= 4 else "5~9" if p["comments"] <= 9 else "10+"
    g.setdefault(b, []).append(sum(p["views"].values()))
print("\n[댓글 구간별 글 수, 조회수 순위권 비율, 글당 평균 조회수(순위권 밖은 0으로 계산)]")
for b in ["0~1", "2~4", "5~9", "10+"]:
    v = g.get(b, [])
    if v: print("  댓글 %-4s 글 %3d편  순위권 %3d%%  평균 %6.0f" % (b, len(v), 100 * sum(1 for x in v if x) / len(v), sum(v) / len(v)))
print("\n[조회수 상위 12편 (3개월 합산)와 댓글]")
for p in by[:12]: print("  %6d  댓글 %2d  %s %s" % (sum(p["views"].values()), p["comments"], p["date"], p["title"][:34]))
print("\n[댓글은 많은데 조회수 순위권 밖인 글 / 조회수는 큰데 댓글 적은 글]")
for p in [p for p in topc if not p["views"]][:5]: print("  댓글 %2d 조회 없음  %s %s" % (p["comments"], p["date"], p["title"][:34]))
for p in [p for p in by[:40] if p["comments"] <= 2][:6]: print("  조회 %6d 댓글 %d  %s %s" % (sum(p["views"].values()), p["comments"], p["date"], p["title"][:34]))
