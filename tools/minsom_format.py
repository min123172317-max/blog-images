#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""민솜 서식 변환 스크립트

원고(순수 텍스트) + 지시 파일(형광펜·사진 위치)을 받아
기존 '민솜 모바일 자동서식' 틀 그대로 한 줄짜리 HTML을 만든다.

실행:
    python3 tools/minsom_format.py 원고.txt 지시.txt -o index.html
    python3 tools/minsom_format.py 원고.txt -o index.html      # 형광펜·사진 없이 서식만

지시 파일 형식 (한 줄에 하나, 순서 무관, '#'으로 시작하면 주석):
    제목: 수서광주선 서식                 <- 페이지 탭 제목(원고 제목과 무관, 생략 가능)
    폴더: 261114-suseo-gwangju            <- blog-images 저장소 안 사진 폴더
    빨: 수서광주선에 필요한 속도는        <- 그 글자가 들어간 '문장 전체'를 빨강으로
    노: 청량리로 모이던 열차의            <- 노랑
    초: 동쪽은 여주~원주                  <- 초록
    파: 정거장이 세 곳뿐인                <- 파랑
    사진: 01.jpg | 청량리로 모이던 열차의 <- 그 글자가 들어간 문단 '뒤'에 사진
    사진: 02.jpg | 3-2                    <- 소제목 3의 2번째 문단 뒤 (0-1 = 서문 1번째 문단)

글자 조각은 원고에서 딱 한 곳에만 있어야 한다(없거나 여러 곳이면 오류로 멈춤).
"""
import argparse
import html
import re
import sys

REPO_RAW = "https://raw.githubusercontent.com/min123172317-max/blog-images/main"

COLORS = {
    "빨": "#ffcdc0", "빨강": "#ffcdc0",
    "노": "#fff8b2", "노랑": "#fff8b2",
    "초": "#c2f4db", "초록": "#c2f4db",
    "파": "#b0f1ff", "파랑": "#b0f1ff",
}
COLOR_NAME = {"#ffcdc0": "빨강", "#fff8b2": "노랑", "#c2f4db": "초록", "#b0f1ff": "파랑"}

# 단축어 '리치 텍스트를 URL로 변환할 수 없음' 오류를 막기 위해 코드 표기로 바꾸는 영문 약어
ENTITY_WORDS = ["AMAT"]

BL = '<p style="margin:0;"><br></p>'
HR = '<hr style="border:0;border-top:1px solid #aaa;margin:30px 0;">'
CENTER_TITLE = '<p style="text-align:center;font-size:18px;font-weight:700;margin:0;">%s</p>'
SCRIPT = ('<script>function selectArticle(){var el=document.getElementById("article");'
          'var r=document.createRange();r.selectNodeContents(el);var s=window.getSelection();'
          's.removeAllRanges();s.addRange(r);}</script>')

SENT_SPLIT = re.compile(r'(?<=[가-힣\)\]"”’\'][.?!])\s+')
NUM_LINE = re.compile(r'^(\d+)\.\s+(.+)$')


def die(msg):
    sys.exit("오류: " + msg)


def esc(text):
    out = html.escape(text, quote=False)
    for w in ENTITY_WORDS:
        out = out.replace(w, "".join("&#%d;" % ord(c) for c in w))
    return out


def clean(line):
    line = line.strip()
    line = re.sub(r'^\*\*(.+)\*\*$', r'\1', line)   # **굵게** 표시 제거
    return line.strip()


def norm(s):
    return re.sub(r'\s+', ' ', s).strip()


def parse_manuscript(text):
    lines = [clean(l) for l in text.replace("\r", "").split("\n")]
    lines = [l for l in lines if l and not re.fullmatch(r'[-=*_]{3,}', l)]

    try:
        i = next(k for k, l in enumerate(lines) if l.startswith("본문 3줄 요약"))
    except StopIteration:
        die("'본문 3줄 요약' 줄을 찾지 못했습니다.")
    title = lines[0] if i > 0 else ""
    i += 1

    summary = []
    while i < len(lines) and len(summary) < 3:
        m = NUM_LINE.match(lines[i])
        if not m:
            die("본문 3줄 요약은 '1. 2. 3.' 번호가 붙은 세 문장이어야 합니다: " + lines[i][:30])
        summary.append(m.group(2))
        i += 1
    if len(summary) != 3:
        die("본문 3줄 요약이 3줄이 아닙니다.")

    if i >= len(lines) or not lines[i].replace(" ", "").startswith("목차"):
        die("3줄 요약 다음에 '목차' 줄이 없습니다.")
    i += 1
    toc = []
    while i < len(lines):
        m = NUM_LINE.match(lines[i])
        if not m or int(m.group(1)) != len(toc) + 1:
            break
        toc.append(lines[i])
        i += 1
    if not toc:
        die("목차 항목을 찾지 못했습니다.")
    toc_set = {norm(t) for t in toc}

    intro, sections, notice, tags = [], [], [], []
    cur = intro
    mode = "body"
    while i < len(lines):
        l = lines[i]
        i += 1
        if l.startswith("#") and not l.startswith("# "):
            tags.append(l)
            continue
        if l.replace(" ", "") in ("네이버태그", "태그"):
            continue
        if mode == "notice" and re.match(r'^(공식 원문 대조|정정 사항|수정할 부분)', l):
            break                                   # 원고 뒤에 붙은 납품 메모는 버림
        if l.startswith("투자 유의사항"):
            mode = "notice"
            rest = l[len("투자 유의사항"):].lstrip(" :：")
            if rest:
                notice.append(rest)
            continue
        if mode == "notice":
            notice.append(l)
            continue
        m = NUM_LINE.match(l)
        if m and (norm(l) in toc_set or
                  (int(m.group(1)) == len(sections) + 1 and len(l) < 70 and not l.endswith("."))):
            sections.append({"title": l, "paras": []})
            cur = sections[-1]["paras"]
            continue
        cur.append(l)

    if len(sections) != len(toc):
        die("목차는 %d개인데 본문 소제목은 %d개입니다." % (len(toc), len(sections)))
    if not notice:
        die("'투자 유의사항'을 찾지 못했습니다.")
    return {"title": title, "summary": summary, "toc": toc, "intro": intro,
            "sections": sections, "notice": " ".join(notice), "tags": " ".join(tags)}


def parse_spec(text):
    spec = {"title": "", "folder": "", "marks": [], "photos": []}
    for n, raw in enumerate(text.replace("\r", "").split("\n"), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            die("지시 파일 %d번째 줄에 ':'가 없습니다: %s" % (n, line[:30]))
        key, val = line.split(":", 1)
        key, val = key.strip(), val.strip()
        if key == "제목":
            spec["title"] = val
        elif key == "폴더":
            spec["folder"] = val.strip("/")
        elif key in COLORS:
            spec["marks"].append((COLORS[key], val))
        elif key == "사진":
            if "|" not in val:
                die("지시 파일 %d번째 줄: '사진: 파일명 | 위치' 형식이어야 합니다." % n)
            fname, where = [v.strip() for v in val.split("|", 1)]
            spec["photos"].append((fname, where))
        else:
            die("지시 파일 %d번째 줄: 모르는 항목 '%s'" % (n, key))
    return spec


def build(ms, spec):
    # blocks[k] = 서문(k=0) 또는 소제목 k의 문단 목록
    blocks = [ms["intro"]] + [s["paras"] for s in ms["sections"]]
    marks = {}    # (블록, 문단) -> [(문장번호, 색)]
    photos = {}   # (블록, 문단) -> [주소]
    warns = []

    def find_para(snip):
        hits = [(b, p) for b, paras in enumerate(blocks)
                for p, t in enumerate(paras) if snip in t]
        if not hits:
            die("원고에서 찾을 수 없는 글자 조각: " + snip)
        if len(hits) > 1:
            die("여러 문단에 있는 글자 조각(더 길게 적어 주세요): " + snip)
        return hits[0]

    for color, snip in spec["marks"]:
        b, p = find_para(snip)
        sents = SENT_SPLIT.split(blocks[b][p])
        idx = [k for k, s in enumerate(sents) if snip in s]
        if len(idx) != 1:
            die("한 문장으로 좁혀지지 않는 글자 조각(문장 안쪽 글자로 적어 주세요): " + snip)
        marks.setdefault((b, p), []).append((idx[0], color))

    for fname, where in spec["photos"]:
        m = re.fullmatch(r'(\d+)-(\d+)', where)
        if m:
            b, p = int(m.group(1)), int(m.group(2)) - 1
            if b >= len(blocks) or p < 0 or p >= len(blocks[b]):
                die("사진 위치가 원고 범위를 벗어납니다: " + where)
        else:
            b, p = find_para(where)
        if re.match(r'^https?://', fname):
            url = fname
        else:
            if not spec["folder"]:
                die("사진을 쓰려면 지시 파일에 '폴더:' 줄이 필요합니다.")
            url = "%s/%s/%s" % (REPO_RAW, spec["folder"], fname)
        photos.setdefault((b, p), []).append(url)

    def render_block(b):
        out = []
        for p, text in enumerate(blocks[b]):
            sents = SENT_SPLIT.split(text)
            colored = dict(marks.get((b, p), []))
            parts = [('<mark style="background:%s;font-weight:700;">%s</mark>' % (colored[k], esc(s)))
                     if k in colored else esc(s) for k, s in enumerate(sents)]
            out.append('<p style="margin:0;">%s</p>' % " ".join(parts))
            for url in photos.get((b, p), []):
                out.append('<p style="margin:0;text-align:center;"><img src="%s" alt="" '
                           'style="max-width:100%%;height:auto;"></p>' % url)
        return BL.join(out)

    # ---- 규칙 점검(멈추지 않고 알림만) ----
    for b in range(len(blocks)):
        name = "서문" if b == 0 else "소제목 %d" % b
        cols = [c for (bb, p), lst in marks.items() if bb == b for _, c in lst]
        red = cols.count("#ffcdc0")
        sub = cols.count("#c2f4db") + cols.count("#b0f1ff")
        nphoto = sum(len(v) for (bb, p), v in photos.items() if bb == b)
        if spec["marks"]:
            if b == 0 and red != 1:
                warns.append("%s: 빨강 %d개 (1개여야 함)" % (name, red))
            if b > 0 and not 1 <= red <= 2:
                warns.append("%s: 빨강 %d개 (1~2개여야 함)" % (name, red))
            if sub > 2:
                warns.append("%s: 초록+파랑 %d개 (최대 2개, 나열 문장 초록은 예외)" % (name, sub))
        if spec["photos"] and b > 0 and not 1 <= nphoto <= 2:
            warns.append("%s: 사진 %d장 (1~2장이어야 함)" % (name, nphoto))
        for p in range(len(blocks[b])):
            pc = [c for _, c in marks.get((b, p), [])]
            if "#ffcdc0" in pc and "#fff8b2" in pc:
                warns.append("%s %d번째 문단: 빨강과 노랑이 함께 있음" % (name, p + 1))
            if pc.count("#fff8b2") > 1:
                warns.append("%s %d번째 문단: 노랑 2개 이상" % (name, p + 1))
            for c in ("#ffcdc0", "#b0f1ff"):
                if pc.count(c) > 1:
                    warns.append("%s %d번째 문단: %s 2개 이상" % (name, p + 1, COLOR_NAME[c]))
            if len(set(pc)) >= 3:
                warns.append("%s %d번째 문단: 색이 3가지 이상 겹침" % (name, p + 1))

    page_title = spec["title"] or "민솜 서식"
    h = ['<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">'
         '<meta name="viewport" content="width=device-width,initial-scale=1">'
         '<title>%s</title></head>' % esc(page_title),
         '<body style="font-family:\'Nanum Gothic\',\'나눔고딕\',sans-serif;padding:22px;'
         'font-size:16px;line-height:1.9;color:#111;margin:0;">',
         '<button onclick="selectArticle()" style="font-size:18px;padding:10px 18px;'
         'margin-bottom:18px;">원고 전체 선택</button>',
         '<div id="article">',
         CENTER_TITLE % "본문 3줄 요약", BL,
         '<div style="background:#e5f8cd;border:3px solid #000;padding:18px 20px;">'
         '<ol style="margin:0;padding-left:22px;">']
    h += ['<li style="font-weight:700;text-align:justify;">%s</li>' % esc(s) for s in ms["summary"]]
    h += ['</ol></div>', BL, CENTER_TITLE % "목차", BL]
    h += ['<p style="font-size:11px;line-height:1.7;margin:0;">%s</p>' % esc(t) for t in ms["toc"]]
    h += [HR, render_block(0)]
    for k, sec in enumerate(ms["sections"], 1):
        h += [HR, '<p style="font-size:19px;font-weight:700;margin:0;">%s</p>' % esc(sec["title"]),
              BL, render_block(k)]
    h += [HR, '<p style="font-size:11px;font-weight:700;margin:0;">투자 유의사항</p>',
          '<p style="font-size:11px;margin:0;">%s</p>' % esc(ms["notice"])]
    if ms["tags"]:
        h += [BL, '<p style="font-size:13px;line-height:1.8;margin:0;">%s</p>' % esc(ms["tags"])]
    h += ['</div>', SCRIPT, '</body></html>']
    return "".join(h), warns


def main():
    ap = argparse.ArgumentParser(description="민솜 서식 변환")
    ap.add_argument("manuscript")
    ap.add_argument("spec", nargs="?")
    ap.add_argument("-o", "--out", default="index.html")
    a = ap.parse_args()

    try:
        ms = parse_manuscript(open(a.manuscript, encoding="utf-8").read())
        spec = parse_spec(open(a.spec, encoding="utf-8").read() if a.spec else "")
    except OSError as e:
        die("파일을 열 수 없습니다: %s" % e)

    page, warns = build(ms, spec)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(page)

    body = "\n".join([ms["title"]] + ms["summary"] + ms["toc"] + ms["intro"] +
                     [x for s in ms["sections"] for x in [s["title"]] + s["paras"]] + [ms["notice"]])
    print("완료: %s (%d자)" % (a.out, len(page)))
    print("소제목 %d개 / 형광펜 %d개 / 사진 %d장 / 원고 분량 약 %d자(태그 제외)"
          % (len(ms["sections"]), len(spec["marks"]), len(spec["photos"]), len(body)))
    if not ms["tags"]:
        warns.append("태그 줄이 없습니다.")
    for w in warns:
        print("확인 필요 - " + w)


if __name__ == "__main__":
    main()
