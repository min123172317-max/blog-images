#!/usr/bin/env python3
"""원본(서울 글)과 새 글(민솜판)의 문장 겹침 검사 (rules/handoff.md 7-C, 2026-11-25).

사용법:
  python3 tools/overlap_check.py 원본.(txt|html) 새글.(txt|html) [--limit 30]

방법: 공백·문장부호를 뺀 글자 5개 묶음(5-gram) 중 새 글의 묶음이 원본에도 있는 비율(%).
  - 전체 겹침 %  : limit(기본 30%) 이하이면 통과
  - 문단별 겹침 % : 50% 넘는 문단을 표시(이 문단을 다시 씀)
  - 제목·첫 문단 : 30% 넘으면 표시(제목·서문은 새로 써야 함)
끝 코드: 0 통과 / 1 기준 초과 / 2 입력 오류
"""
import argparse
import html
import re
import sys

N = 5
PARA_LIMIT = 50
HEAD_LIMIT = 30


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print(f"[오류] 파일을 열 수 없음: {path} ({e})")
        sys.exit(2)
    if path.lower().endswith((".html", ".htm")) or "<p" in text or "<div" in text:
        text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)
        text = re.sub(r"(?i)<br\s*/?>|</(p|div|h[1-6]|li|tr)>", "\n", text)
        text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return text


def norm(s):
    # 한글·영문·숫자만 남김(공백·문장부호·기호 제거)
    return re.sub(r"[^0-9A-Za-z가-힣]", "", s)


def grams(s):
    s = norm(s)
    return {s[i:i + N] for i in range(len(s) - N + 1)}


def ratio(part, base):
    g = grams(part)
    return round(100 * len(g & base) / len(g), 1) if g else 0.0


def paragraphs(text):
    return [p.strip() for p in re.split(r"\n\s*\n|\n", text) if len(norm(p)) >= 20]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("original")
    ap.add_argument("new")
    ap.add_argument("--limit", type=float, default=30)
    a = ap.parse_args()

    orig, new = load(a.original), load(a.new)
    base = grams(orig)
    if not base or not grams(new):
        print("[오류] 글이 너무 짧거나 비어 있음")
        sys.exit(2)

    total = ratio(new, base)
    paras = paragraphs(new)
    fail = total > a.limit
    print(f"전체 겹침: {total}% (기준 {a.limit:g}% 이하) → {'초과' if fail else '통과'}")

    if paras:
        head = "\n".join(paras[:2])  # 보통 제목 + 첫 문단
        h = ratio(head, base)
        print(f"제목·첫 문단 겹침: {h}% (기준 {HEAD_LIMIT}% 이하)" + (" → 새로 쓰기" if h > HEAD_LIMIT else ""))
        fail = fail or h > HEAD_LIMIT

    bad = [(ratio(p, base), p) for p in paras]
    bad = [(r, p) for r, p in bad if r > PARA_LIMIT]
    if bad:
        print(f"\n다시 쓸 문단 {len(bad)}개 (문단 겹침 {PARA_LIMIT}% 초과):")
        for r, p in sorted(bad, reverse=True):
            print(f"  {r}% | {p[:40]}…")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
