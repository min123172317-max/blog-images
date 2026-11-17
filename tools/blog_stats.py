#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""민솜 글별 반응 수집 (공개 데이터: 공감수 + 댓글수. 조회수는 비공개라 수집 불가)

하는 일
  1) 블로그 글 목록을 발행일 기준으로 읽는다 (제목, 글번호, 발행일, 댓글수)
  2) (선택 --likes) 글별 공감수를 네이버 공감 서버에서 읽는다 — 현재는 비로그인이라 빈 값
  3) data/blog_stats.tsv 에 누적 저장한다 (같은 글은 덮어쓴다 = 중복 없음)
  4) 반응 점수 = 공감 + 댓글 (조회수의 대리값, 2026-11-17 민국 확정). 공감이 비면 댓글만

실행
  python3 tools/blog_stats.py --since 2026-08-01          # 8월 1일부터 지금까지 전부 수집
  python3 tools/blog_stats.py --since 2026-11-10 --until 2026-11-16 --top 10   # 지난주만 보기
  python3 tools/blog_stats.py --report --since 2026-10-01 # 저장된 표로 보고서만 (수집 안 함)
"""
import argparse
import csv
import datetime as dt
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

BLOG_ID = "minsoaa"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "data", "blog_stats.tsv")
FIELDS = ["logNo", "date", "title", "category", "comments", "likes", "score", "fetched"]
KST = dt.timezone(dt.timedelta(hours=9))


def get(url, referer=None, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, **({"Referer": referer} if referer else {})})
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception as e:  # 네트워크 오류는 잠깐 쉬고 다시 시도
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def parse_date(s, today):
    """'2026. 11. 17.' 또는 '8분 전' '3시간 전' '어제' 형태를 날짜로"""
    s = s.strip()
    m = re.match(r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})", s)
    if m:
        return dt.date(int(m[1]), int(m[2]), int(m[3]))
    if "일 전" in s:
        n = int(re.sub(r"\D", "", s) or 1)
        return today - dt.timedelta(days=n)
    return today  # 분/시간 전 = 오늘


def list_posts(since, until):
    today = dt.datetime.now(KST).date()
    out, page = [], 1
    while page <= 80:
        url = ("https://blog.naver.com/PostTitleListAsync.naver?blogId=%s&viewdate=&currentPage=%d"
               "&categoryNo=0&parentCategoryNo=0&countPerPage=30" % (BLOG_ID, page))
        d = json.loads(get(url, "https://blog.naver.com/" + BLOG_ID).replace("\\'", "'"), strict=False)
        posts = d.get("postList", [])
        if not posts:
            break
        oldest = today
        for x in posts:
            day = parse_date(x.get("addDate", ""), today)
            oldest = min(oldest, day)
            if since <= day <= until:
                out.append({
                    "logNo": x["logNo"], "date": day.isoformat(),
                    "title": html.unescape(urllib.parse.unquote_plus(x["title"])),
                    "category": x.get("categoryNo", ""),
                    "comments": int(x.get("commentCount") or 0),
                })
        if oldest < since:
            break
        page += 1
        time.sleep(0.3)
    return out


def likes_for(log_nos):
    """공감수 시도. 2026-11-17 확인: 비로그인 상태에서는 모든 글이 빈 값으로 와서 사실상 못 읽는다.
    (여러 글 묶음 질의는 첫 글만 돌려주므로 한 글씩 묻는다.) 읽히면 합계를, 비었으면 빈 값을 둔다."""
    res = {}
    for n in log_nos:
        url = "https://blog.like.naver.com/v1/search/contents?q=%s&suppress_response_codes=true" % urllib.parse.quote("BLOG[%s_%s]" % (BLOG_ID, n), safe="")
        try:
            c = json.loads(get(url, "https://blog.naver.com/"))["contents"][0]
        except Exception:
            continue
        m = c.get("reactionMap") or {}
        if m:
            res[n] = sum(int(v) for v in m.values() if str(v).isdigit())
        time.sleep(0.2)
    return res


def load():
    if not os.path.exists(OUT):
        return {}
    with open(OUT, encoding="utf-8", newline="") as f:
        return {r["logNo"]: r for r in csv.DictReader(f, delimiter="\t")}


def save(rows):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, delimiter="\t")
        w.writeheader()
        for r in sorted(rows.values(), key=lambda r: (r["date"], r["logNo"]), reverse=True):
            w.writerow({k: r.get(k, "") for k in FIELDS})


def report(rows, since, until, top):
    sel = [r for r in rows.values() if since.isoformat() <= r["date"] <= until.isoformat()]
    if not sel:
        print("해당 기간에 저장된 글이 없습니다.")
        return
    for r in sel:
        r["score"] = int(r["likes"] or 0) + int(r["comments"] or 0)
    sel.sort(key=lambda r: -int(r["score"]))
    print("기간 %s ~ %s · 글 %d편 · 반응 합계 %d (댓글 중심, 공감 %d + 댓글 %d)" % (
        since, until, len(sel), sum(int(r["score"]) for r in sel),
        sum(int(r["likes"] or 0) for r in sel), sum(int(r["comments"] or 0) for r in sel)))
    print("\n[월별]")
    by = {}
    for r in sel:
        by.setdefault(r["date"][:7], []).append(int(r["score"]))
    for m in sorted(by):
        v = by[m]
        print("  %s  글 %3d편  반응 합계 %5d  글당 평균 %.1f" % (m, len(v), sum(v), sum(v) / len(v)))
    print("\n[반응 상위 %d]" % top)
    for i, r in enumerate(sel[:top], 1):
        print("  %2d. %s  공감 %3s 댓글 %3s  %s" % (i, r["date"], r["likes"], r["comments"], r["title"][:48]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-08-01")
    ap.add_argument("--until", default=None)
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--likes", action="store_true", help="공감수도 시도(느리고 현재는 빈 값)")
    ap.add_argument("--report", action="store_true", help="수집 없이 저장된 표로 보고서만")
    a = ap.parse_args()
    since = dt.date.fromisoformat(a.since)
    until = dt.date.fromisoformat(a.until) if a.until else dt.datetime.now(KST).date()
    rows = load()
    if not a.report:
        posts = list_posts(since, until)
        print("글 목록 %d편 읽음" % len(posts))
        lk = likes_for([p["logNo"] for p in posts]) if a.likes else {}
        now = dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M")
        for p in posts:
            p["likes"] = lk.get(p["logNo"], "")
            p["score"] = (int(p["likes"]) if p["likes"] != "" else 0) + p["comments"]
            p["fetched"] = now
            rows[p["logNo"]] = p
        save(rows)
        if not a.likes:
            print("공감수는 비로그인으로 읽히지 않아 댓글 수만 반영합니다(--likes 로 재시도 가능)")
        print("저장: data/blog_stats.tsv (누적 %d편)" % len(rows))
    report(rows, since, until, a.top)


if __name__ == "__main__":
    main()
