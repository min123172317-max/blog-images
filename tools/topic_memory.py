#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""민솜 터진 주제 기억 (웹검색 0회)

하는 일
  1) 블로그 최신 글 목록을 읽어 data/blog_stats.tsv 를 갱신한다 (댓글 수 포함)
  2) data/topic_keywords.tsv 의 메인 키워드(주제)별로 지난 글 성적을 모은다
     - 성적 = 실제 월간 조회수(data/views_monthly.tsv, 민국이 올린 캡처)가 있으면 그것,
       없으면 댓글 수로 추정 (댓글 10개 이상 = 터짐, 5~9개 = 보통. 2026-11-17 검증: 댓글 10+ 글은 전부 조회수 순위권)
  3) "다시 쓸 때가 된 터진 주제", "쉬는 주제", "특집 후보", "안 터지는 주제"를 짧게 보여 준다

실행
  python3 tools/topic_memory.py            # 글감 찾기 전에 한 번 (기본)
  python3 tools/topic_memory.py --week     # 지난 7일 글 성적표 (월요일 주간 분석용)
  python3 tools/topic_memory.py --month 2026-11   # 그 달 글 성적표 (매월 1일 분석용)
  python3 tools/topic_memory.py --offline  # 블로그를 다시 읽지 않고 저장된 표만 사용
"""
import argparse
import csv
import datetime as dt
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import blog_stats as bs  # noqa: E402

D = os.path.join(HERE, "..", "data")
HIT, MID = 3000, 1000          # 한 달 조회수 기준: 터짐 / 보통
HIT_C, MID_C = 10, 5           # 조회수 자료가 없을 때 댓글 기준
norm = lambda s: re.sub(r"[^0-9A-Za-z가-힣]", "", s)


def refresh(rows):
    """최근 글만 다시 읽어 표를 갱신한다. 실패하면 저장된 표를 그대로 쓴다."""
    today = dt.datetime.now(bs.KST).date()
    last = max((r["date"] for r in rows.values()), default="2026-07-01")
    since = dt.date.fromisoformat(last) - dt.timedelta(days=21)  # 댓글은 뒤늦게 붙으므로 3주치 다시 읽음
    try:
        now = dt.datetime.now(bs.KST).strftime("%Y-%m-%d %H:%M")
        for p in bs.list_posts(since, today):
            p["likes"] = ""; p["score"] = p["comments"]; p["fetched"] = now
            rows[p["logNo"]] = p
        bs.save(rows)
    except Exception as e:
        print("(블로그 글 목록을 새로 읽지 못해 저장된 표로 계산합니다: %s)" % e)
    return rows


def load_all(offline):
    rows = bs.load()
    if not offline:
        rows = refresh(rows)
    posts = list(rows.values())
    for p in posts:
        p["n"] = norm(p["title"]); p["c"] = int(p["comments"] or 0); p["v"] = {}
    vp = os.path.join(D, "views_monthly.tsv")
    months = set()
    if os.path.exists(vp):
        for v in csv.DictReader(open(vp, encoding="utf-8"), delimiter="\t"):
            months.add(v["month"])
            pre = norm(v["title_prefix"])
            c = [p for p in posts if p["date"] == v["date"] and p["n"].startswith(pre[:6])]
            if len(c) != 1:
                c = [p for p in posts if p["date"] == v["date"] and pre[:4] in p["n"]]
            if len(c) == 1:
                c[0]["v"][v["month"]] = int(v["views"])
    for p in posts:
        best = max(p["v"].values(), default=0)
        known = p["date"][:7] in months          # 그 글이 올라온 달의 조회수 표가 있는가
        if best >= HIT or (not known and p["c"] >= HIT_C):
            p["tier"] = "터짐"
        elif best >= MID or (not known and p["c"] >= MID_C):
            p["tier"] = "보통"
        else:
            p["tier"] = "약함"
        p["best"] = best; p["est"] = not known
    themes = []
    for t in csv.DictReader(open(os.path.join(D, "topic_keywords.tsv"), encoding="utf-8"), delimiter="\t"):
        pats = [[norm(y) for y in x.split("+")] for x in t["patterns"].split("|") if x.strip()]   # a+b = 둘 다 포함
        ps = [p for p in posts if any(all(y in p["n"] for y in x) for x in pats)]
        themes.append({"name": t["theme"], "cycle": int(t["cycle_days"] or 0), "note": t.get("note", ""), "posts": ps})
    return posts, themes


def label(p):
    return ("조회 %d" % p["best"]) if p["best"] else ("댓글 %d%s" % (p["c"], "(추정)" if p["est"] else ""))


def memory(posts, themes):
    today = dt.datetime.now(bs.KST).date()
    good, over, special, weak = [], [], [], []
    for t in themes:
        ps = t["posts"]
        if not ps:
            continue
        hits = [p for p in ps if p["tier"] == "터짐"]
        mids = [p for p in ps if p["tier"] == "보통"]
        lastp = max(ps, key=lambda p: p["date"])
        days = (today - dt.date.fromisoformat(lastp["date"])).days
        topp = max(ps, key=lambda p: (p["best"], p["c"]))
        rate = (len(hits) + 0.5 * len(mids)) / len(ps)      # 적중률: 터짐 1점, 보통 0.5점
        row = (t, len(ps), len(hits), len(mids), days, lastp, topp, rate)
        if t["cycle"] == 0 or not hits:
            weak.append(row)
        elif rate >= 0.35:
            good.append(row)
        else:
            over.append(row)
        if len(hits) >= 3:
            special.append(row)
    print("== 1. 적중률 높은 주제 (우선 추천. ★ = 주기가 지나 지금 다시 쓸 때) ==")
    for t, n, h, m, days, lastp, topp, rate in sorted(good, key=lambda r: (r[4] < r[0]["cycle"], -r[7])):
        when = "★ 다시 쓸 때" if days >= t["cycle"] else "%d일 뒤" % (t["cycle"] - days)
        print("%s | 터짐 %d·보통 %d / %d편 | 마지막 글 %s(%d일 전) | %s | 최고: %s %s"
              % (t["name"], h, m, n, lastp["date"][5:], days, when, label(topp), topp["title"][:22]))
    print("\n== 2. 많이 썼지만 적중률 낮은 주제 (새 사건·새 각도가 있을 때만) ==")
    print(", ".join("%s(터짐 %d/%d편)" % (r[0]["name"], r[2], r[1]) for r in sorted(over, key=lambda r: -r[1])) or "(없음)")
    print("\n== 3. 특집·연재 후보 (터진 글 3편 이상인 주제. 이미 다룬 각도는 피함) ==")
    for t, n, h, m, days, lastp, topp, rate in sorted(special, key=lambda r: -r[2]):
        print("- %s: %s" % (t["name"], " / ".join(p["title"][:18] for p in
              sorted([p for p in t["posts"] if p["tier"] == "터짐"], key=lambda p: -p["best"])[:4])))
    print("\n== 4. 안 터지는 주제 (추천 제외) ==")
    print(", ".join("%s(터짐 %d/%d편)" % (r[0]["name"], r[2], r[1]) for r in weak) or "(없음)")
    seen = set(id(p) for t in themes for p in t["posts"])
    loose = [p for p in posts if id(p) not in seen and p["tier"] == "터짐"]
    if loose:
        print("\n== 5. 키워드 창고에 없는 터진 글 (data/topic_keywords.tsv 에 주제 추가) ==")
        for p in sorted(loose, key=lambda p: -p["best"])[:6]:
            print("- %s %s %s" % (p["date"], label(p), p["title"][:40]))


def report(posts, themes, since, until, name):
    sel = [p for p in posts if since <= p["date"] <= until]
    print("== %s 글 성적표 (%s ~ %s, %d편) ==" % (name, since, until, len(sel)))
    if not sel:
        print("(글 없음)"); return
    for tier in ["터짐", "보통", "약함"]:
        g = sorted([p for p in sel if p["tier"] == tier], key=lambda p: (-p["best"], -p["c"]))
        print("[%s %d편]" % (tier, len(g)))
        for p in g[: 12 if tier != "약함" else 6]:
            print("  %s %s | %s" % (p["date"][5:], label(p), p["title"][:44]))
    print("댓글 합계 %d, 글당 %.1f, 적중률(터짐+보통) %d%%" % (
        sum(p["c"] for p in sel), sum(p["c"] for p in sel) / len(sel),
        100 * sum(1 for p in sel if p["tier"] != "약함") / len(sel)))
    print("[주제별]")
    for t in themes:
        ps = [p for p in t["posts"] if since <= p["date"] <= until]
        if ps:
            print("  %s: %d편, 터짐 %d·보통 %d" % (t["name"], len(ps),
                  sum(1 for p in ps if p["tier"] == "터짐"), sum(1 for p in ps if p["tier"] == "보통")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", action="store_true")
    ap.add_argument("--month")
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()
    posts, themes = load_all(a.offline)
    today = dt.datetime.now(bs.KST).date()
    if a.week:
        report(posts, themes, (today - dt.timedelta(days=7)).isoformat(), (today - dt.timedelta(days=1)).isoformat(), "지난 7일")
    elif a.month:
        y, m = map(int, a.month.split("-"))
        end = (dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1)).isoformat()
        report(posts, themes, "%04d-%02d-01" % (y, m), end, a.month)
    else:
        memory(posts, themes)


if __name__ == "__main__":
    main()
