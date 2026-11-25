#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""민솜 서식 변환 스크립트

원고(순수 텍스트) + 지시 파일(형광펜·사진 위치)을 받아
민솜 모바일 자동서식 틀(v2, 2026-11-15)로 한 줄짜리 HTML을 만든다.

v2 원고 순서: 제목 → 서문 → '본문 3줄 요약'(1. 2. 3.) → 소제목('1. …') → 투자 유의사항 → 태그
 - 목차는 쓰지 않는다(옛 원고에 있으면 자동으로 버림). 옛 순서(요약이 서문 앞)도 그대로 읽는다.
 - 화면 순서는 항상 서문 → 3줄 요약 상자 → 소제목.
 - 본문 16px(2026-11-15 19px→16px 되돌림), 소제목 24px.
 - 표: 원고에서 '|'로 시작하는 줄을 연달아 쓰면 표 1개가 된다(첫 줄이 머리줄, 연두 #e5f8cd).
       열 3개 이하·칸당 8자 이내(4열이면 5자) — 넘으면 '확인 필요' 알림. '| --- |' 구분줄은 버린다.
       | 구분 | 분양가 | 주변 시세 |
       | 84 타입 | 6억 | 8억 |
 - 썸네일 00.jpg도 서식 페이지 본문에 넣는다(rules/image.md 4-2, 2026-11-17 확정): 서문 2문단 이상이면 '0-1', 1문단이면 '0-0'.
   단, 재개발·재건축 글의 조감도 썸네일은 본문에 넣지 않는다(지시 파일에 00.jpg 줄을 쓰지 않음, 따로 납품).

서울 블로그 원고(2026-11-17, rules/seoul.md 6-4): '본문 3줄 요약' 대신 '한눈에 보기' 줄 + 아래 5줄("항목: 내용"),
'투자 유의사항' 대신 '확인 기준·유의사항'. 상자는 민솜과 같은 초록 상자에 번호 없이 5줄(2026-11-17). 원고에 '한눈에 보기' 줄이 있으면 자동으로 서울 모드가 된다(옵션 없음).

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
    사진: 00.jpg | 0-0                    <- 'N-0' = 그 소제목 첫 문단 바로 위(서문이 1문단일 때 썸네일 자리)
    ※ 마지막 문단 뒤에는 사진을 둘 수 없다(오류로 멈춤, 2026-11-17). 문단과 문단 사이에만 둔다.

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
CENTER_TITLE = '<p style="text-align:center;font-size:19px;font-weight:700;margin:0;">%s</p>'
SCRIPT = ('<script>function selectArticle(){var el=document.getElementById("article");'
          'var r=document.createRange();r.selectNodeContents(el);var s=window.getSelection();'
          's.removeAllRanges();s.addRange(r);}</script>')

SENT_SPLIT = re.compile(r'(?<=[가-힣\)\]"”’\'][.?!])\s+')
NUM_LINE = re.compile(r'^(\d+)\.\s+(.+)$')
TABLE_MARK = "\x00TABLE\x00"


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

    seoul = any(l.replace(" ", "").startswith("한눈에보기") for l in lines)
    head, notice_label = ("한눈에 보기", "확인 기준·유의사항") if seoul else ("본문 3줄 요약", "투자 유의사항")
    try:
        si = next(k for k, l in enumerate(lines) if l.replace(" ", "").startswith(head.replace(" ", "")))
    except StopIteration:
        die("'%s' 줄을 찾지 못했습니다." % head)
    title = lines[0] if si > 0 else ""
    intro = list(lines[1:si])            # v2: 제목과 요약(카드) 사이가 서문
    i = si + 1

    summary = []
    if seoul:                             # 서울: '항목: 내용' 5줄 (번호가 붙어 있으면 떼고 읽음)
        while i < len(lines) and len(summary) < 5:
            l = NUM_LINE.match(lines[i]).group(2) if NUM_LINE.match(lines[i]) else lines[i]
            if not re.match(r"^[^:：]{1,12}[:：]", l):
                die("한눈에 보기는 '항목: 내용' 5줄이어야 합니다: " + lines[i][:30])
            summary.append(l)
            i += 1
        if len(summary) != 5:
            die("한눈에 보기가 5줄이 아닙니다.")
    else:
        while i < len(lines) and len(summary) < 3:
            m = NUM_LINE.match(lines[i])
            if not m:
                die("본문 3줄 요약은 '1. 2. 3.' 번호가 붙은 세 문장이어야 합니다: " + lines[i][:30])
            summary.append(m.group(2))
            i += 1
        if len(summary) != 3:
            die("본문 3줄 요약이 3줄이 아닙니다.")

    toc_set = set()
    if i < len(lines) and lines[i].replace(" ", "").startswith("목차"):
        i += 1                            # 옛 원고의 목차는 읽고 버린다
        n = 0
        while i < len(lines):
            m = NUM_LINE.match(lines[i])
            if not m or int(m.group(1)) != n + 1:
                break
            toc_set.add(norm(lines[i]))
            n += 1
            i += 1

    sections, notice, tags = [], [], []
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
        if mode == "notice" and re.match(r'^(공식 원문 대조|정정 사항|수정할 부분|연관 키워드)', l):
            break                                   # 원고 뒤에 붙은 납품 메모는 버림
        if l.startswith(notice_label) or (seoul and l.startswith("확인 기준")):
            mode = "notice"
            rest = re.sub(r"^확인 기준(·유의사항)?|^투자 유의사항", "", l).lstrip(" :：")
            if rest:
                notice.append(rest)
            continue
        if mode == "notice":
            notice.append(l)
            continue
        if l.startswith("|"):                       # 표 줄
            if cur and cur[-1].startswith(TABLE_MARK):
                cur[-1] += "\n" + l
            else:
                cur.append(TABLE_MARK + l)
            continue
        m = NUM_LINE.match(l)
        if m and (norm(l) in toc_set or
                  (int(m.group(1)) == len(sections) + 1 and len(l) < 70 and not l.endswith("."))):
            sections.append({"title": l, "paras": []})
            cur = sections[-1]["paras"]
            continue
        cur.append(l)

    if not sections:
        die("소제목('1. …')을 찾지 못했습니다.")
    if not notice:
        die("'%s'을 찾지 못했습니다." % notice_label)
    return {"seoul": seoul, "notice_label": notice_label, "title": title, "summary": summary, "intro": intro,
            "sections": sections, "notice": " ".join(notice), "tags": " ".join(tags)}


def table_rows(raw):
    rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in raw.split("\n")]
    # 마크다운 구분줄(| --- | --- |)은 버린다
    return [r for r in rows if not all(re.fullmatch(r":?-{2,}:?", c) for c in r if c)]


def render_table(raw):
    rows = table_rows(raw)
    out = ['<table style="border-collapse:collapse;width:100%;font-size:15px;line-height:1.5;">']
    for k, cells in enumerate(rows):
        style = "border:1px solid #999;padding:6px 8px;text-align:center;"
        if k == 0:
            style += "font-weight:700;background:#e5f8cd;"
        out.append("<tr>" + "".join('<td style="%s">%s</td>' % (style, esc(c)) for c in cells) + "</tr>")
    out.append("</table>")
    return "".join(out)


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


READ_MORE = "함께 읽으면 좋은 글입니다."


def build(ms, spec):
    # '함께 읽으면 좋은 글입니다.' 줄은 원고에 있든 없든 본문 맨 끝에 한 번만, 굵게+밑줄로 넣는다(2026-11-15)
    for sec in ms["sections"]:
        sec["paras"] = [t for t in sec["paras"] if t.replace(" ", "") != READ_MORE.replace(" ", "")]
    # blocks[k] = 서문(k=0) 또는 소제목 k의 문단 목록
    blocks = [ms["intro"]] + [s["paras"] for s in ms["sections"]]
    marks = {}    # (블록, 문단) -> [(문장번호, 색)]
    photos = {}   # (블록, 문단) -> [주소]
    warns = []

    def find_para(snip):
        hits = [(b, p) for b, paras in enumerate(blocks)
                for p, t in enumerate(paras) if not t.startswith(TABLE_MARK) and snip in t]
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
            b, p = int(m.group(1)), int(m.group(2)) - 1   # 'N-0' = 그 소제목(0=서문) 첫 문단 바로 위(p=-1)
            if b >= len(blocks) or p < -1 or p >= len(blocks[b]):
                die("사진 위치가 원고 범위를 벗어납니다: " + where)
        else:
            b, p = find_para(where)
        if p != -1 and p == len(blocks[b]) - 1:   # 2026-11-17 민국 피드백: 마지막 문단 밑 사진은 연속성이 깨짐
            die("사진은 소제목(서문 포함)의 마지막 문단 밑에 둘 수 없습니다(문단과 문단 사이에 두세요): %s | %s"
                % (fname, where))
        if re.match(r'^https?://', fname):
            url = fname
        else:
            if not spec["folder"]:
                die("사진을 쓰려면 지시 파일에 '폴더:' 줄이 필요합니다.")
            url = "%s/%s/%s" % (REPO_RAW, spec["folder"], fname)
        photos.setdefault((b, p), []).append(url)

    def render_block(b):
        out = ['<p style="margin:0;text-align:center;"><img src="%s" alt="" '
               'style="max-width:100%%;height:auto;"></p>' % u for u in photos.get((b, -1), [])]
        for p, text in enumerate(blocks[b]):
            if text.startswith(TABLE_MARK):
                out.append(render_table(text[len(TABLE_MARK):]))
                for url in photos.get((b, p), []):   # 2026-11-25: 표 뒤 사진이 빠지던 오류 수정
                    out.append('<p style="margin:0;text-align:center;"><img src="%s" alt="" '
                               'style="max-width:100%%;height:auto;"></p>' % url)
                continue
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
         '<div id="article">']
    if ms["intro"]:
        h += [render_block(0), HR]
    if ms["seoul"]:   # 서울(2026-11-17 민국 확정): 민솜과 같은 초록 상자, 번호 없이 '항목: 내용' 5줄을 원고 그대로 굵게
        h += [CENTER_TITLE % "한눈에 보기", BL,
              '<div style="background:#e5f8cd;border:3px solid #000;padding:18px 20px;">']
        h += ['<p style="margin:0;font-weight:700;text-align:justify;">%s</p>' % esc(s_) for s_ in ms["summary"]]
        h += ['</div>']
    else:
        h += [CENTER_TITLE % "본문 3줄 요약", BL,
              '<div style="background:#e5f8cd;border:3px solid #000;padding:18px 20px;">'
              '<ol style="margin:0;padding-left:22px;">']
        h += ['<li style="font-weight:700;text-align:justify;">%s</li>' % esc(s) for s in ms["summary"]]
        h += ['</ol></div>']
    for k, sec in enumerate(ms["sections"], 1):
        h += [HR, '<p style="font-size:24px;font-weight:700;margin:0;">%s</p>' % esc(sec["title"]),
              BL, render_block(k)]
    h += [BL, '<p style="margin:0;"><b><u>%s</u></b></p>' % esc(READ_MORE)]
    h += [HR, '<p style="font-size:11px;font-weight:700;margin:0;">%s</p>' % esc(ms["notice_label"]),
          '<p style="font-size:11px;margin:0;">%s</p>' % esc(ms["notice"])]
    if ms["tags"]:
        h += [BL, '<p style="font-size:13px;line-height:1.8;margin:0;">%s</p>' % esc(ms["tags"])]
    h += ['</div>', SCRIPT, '</body></html>']
    return "".join(h), warns


# 2026-11-25 주간 최적화: 글쓰기 세부 규칙을 기계 점검으로 옮김(rules/write.md '자동 점검' 표).
BANNED = ["SRT", "결절점", "총정리", "진짜 이유", "앞으로의 전망", "여러분은 어떻게", "정리하며"]
# AI 티 나는 상투 표현(2026-11-25 민국 지적: "글이 너무 AI가 쓴 것 같다"). 2곳 이상이면 알림.
AI_PHRASES = ["셈입니다", "라는 점입니다", "주목할 ", "눈여겨볼", "살펴보겠습니다", "짚어봤습니다", "짚어보겠습니다",
              "알아보겠습니다", "의미합니다", "다시 말해", "한마디로", "무엇보다", "이처럼", "그렇다면",
              "열쇠", "신호탄", "숨은 승자", "판도", "의 무게", "그림이 달라", "시계가", "답은 ", "핵심은 "]
READER_TOWNS = "동탄|화성|병점|봉담|향남|수원|영통|광교|매교|용인|기흥|수지|처인|남사|성남|분당|판교|야탑|위례|평택|지제|고덕|오산"


def review(ms, paras_all):
    """원고 점검. (경고 목록, 분량) 반환. 원고는 고치지 않는다."""
    warns = []
    body = "\n".join([ms["title"]] + ms["summary"] + [s["title"] for s in ms["sections"]] +
                     [x.replace(TABLE_MARK, "") for x in paras_all] +
                     ([ms["notice"]] if ms["seoul"] else []))   # 2026-11-19: 민솜 분량에서 투자 유의사항 제외
    text_only = "\n".join([ms["title"]] + ms["summary"] + [x for x in paras_all if not x.startswith(TABLE_MARK)])
    # ---- 제목 ----
    if len(ms["title"]) > 40:
        warns.append("제목 %d자 (40자 이내여야 함)" % len(ms["title"]))
    if len(re.findall(r"\d[\d,.]*", ms["title"])) > 2 or "→" in ms["title"]:
        warns.append("제목에 숫자가 많거나 '→'가 있음 (숫자는 1개, 나열 금지)")
    if not ms["seoul"] and not re.search(READER_TOWNS, ms["title"]):
        warns.append("제목에 독자 동네 이름(동탄·수원·용인·화성 등)이 없음 — 경기남부 밖 주제는 '동탄' 필수")
    # ---- 금지 표기 ----
    for w in BANNED:
        n = body.count(w)
        if n:
            warns.append("금지 표기 '%s' %d곳%s" % (w, n, " — 고속열차는 KTX로" if w == "SRT" else ""))
    fp = re.findall(r"(?<![가-힣])(저는|제가|필자는)|(라고 봅니다|라고 생각합니다)", body)
    fp = [a or b for a, b in fp]
    if fp:   # 2026-11-17 민국 확정: 1인칭·'~라고 봅니다' 금지
        warns.append("1인칭 표현 %d곳 (%s) — 단정형 결론으로 바꿔야 함" % (len(fp), ", ".join(sorted(set(fp)))))
    # ---- AI 티 ----
    hits = [(w, text_only.count(w)) for w in AI_PHRASES if text_only.count(w)]
    if sum(n for _, n in hits) >= 2:
        warns.append("AI 티 표현 %d곳 (%s) — 사실 문장으로 바꿈" % (sum(n for _, n in hits), ", ".join("%s×%d" % h for h in hits)))
    na = len(re.findall(r"이 아니라|가 아니라", text_only))
    if na > 2:
        warns.append("'A가 아니라 B' 문형 %d곳 (글당 2곳 이내)" % na)
    sents = [x for p in paras_all if not p.startswith(TABLE_MARK) for x in SENT_SPLIT.split(p) if x.strip()]
    longs = [x for x in sents if len(x) > 80]
    if longs:
        warns.append("80자 넘는 문장 %d개 (한 문장에 한 내용) 예: %s…" % (len(longs), longs[0][:25]))
    rq = [x for x in sents if x.rstrip().endswith("?")]
    if rq:
        warns.append("본문 물음표 문장 %d개 (본문은 평서문, 질문은 소제목에만)" % len(rq))
    # ---- 구조 ----
    if ms["seoul"]:   # 서울 규격: 소제목 5~6개, 3,500~5,500자 (rules/seoul.md 6-4)
        if not 5 <= len(ms["sections"]) <= 6:
            warns.append("소제목 %d개 (서울 글은 5~6개)" % len(ms["sections"]))
        if not 3500 <= len(body) <= 5500:
            warns.append("분량 약 %d자 (서울 글은 3,500~5,500자)" % len(body))
    else:
        if len(ms["sections"]) > 6:
            warns.append("소제목 %d개 (적중형 5개, 검색형 3~4개)" % len(ms["sections"]))
        if len(body) > 5000 or len(body) < 4000:   # 2026-11-24 민국: 기본 4,000~4,500자, "깊게"면 5,000자
            warns.append("분량 약 %d자 (기본 4,000~4,500자, '깊게'면 5,000자까지, 4,000자 미만 금지)" % len(body))
    # 2026-11-25 민국 긴급 수정: 소제목은 명사형·'~한 이유'로 끝냄. '~나요'·'~까요' 같은 '~요' 질문 어미 금지.
    yo = [s["title"] for s in ms["sections"] if re.sub(r"[?？\s]+$", "", s["title"]).endswith("요")]
    if yo:
        warns.append("소제목 '~요' 어미 %d개 (명사형이나 '~한 이유'로 끝냄) 예: %s" % (len(yo), yo[0][:25]))
    sizes = []
    for sec in ms["sections"]:
        n = len(sec["title"]) + sum(len(x.replace(TABLE_MARK, "")) for x in sec["paras"])
        sizes.append(n)
        if n > 1100:   # 2026-11-24: 소제목 800~1,000자, 최대 1,100자
            warns.append("소제목 '%s' %d자 (최대 1,100자, 넘으면 둘로 나눔)" % (sec["title"][:15], n))
    if len(sizes) > 1 and min(sizes) and max(sizes) > min(sizes) * 1.5:
        warns.append("소제목 길이 차이 큼: 가장 긴 것 %d자 / 가장 짧은 것 %d자 (1.5배 이내)" % (max(sizes), min(sizes)))
    if ms["sections"]:
        last = [x for x in ms["sections"][-1]["paras"] if not x.startswith(TABLE_MARK)]
        if last and last[-1].rstrip().endswith("?"):
            warns.append("마지막 문장이 의문문 — 단정형 결론 + 이유로 끝냄")
    arts = set(re.findall(r"제\d+조(?:의\d+)?", text_only))
    if len(arts) > 1:
        warns.append("법 조문 번호 %d종 (%s) — 글당 1개" % (len(arts), ", ".join(sorted(arts))))
    if not ms["seoul"]:   # 2026-11-19 민국 확정: 투자 유의사항은 4~5문장
        nn = len([s for s in SENT_SPLIT.split(ms["notice"].strip()) if s.strip()])
        if nn > 5:
            warns.append("투자 유의사항 %d문장 (4~5문장으로 줄여야 함)" % nn)
    ntab = sum(1 for x in paras_all if x.startswith(TABLE_MARK))
    if ntab > 1:
        warns.append("표 %d개 (글당 최대 1개)" % ntab)
    for x in paras_all:
        if not x.startswith(TABLE_MARK):
            continue
        rows = table_rows(x[len(TABLE_MARK):])
        ncol = max(len(r) for r in rows)
        limit = 8 if ncol <= 3 else 5
        if ncol > 4:
            warns.append("표 열 %d개 (최대 3개, 부득이하면 4개)" % ncol)
        for r in rows:
            for c in r:
                if len(c) > limit:
                    warns.append("표 칸 '%s' %d자 (열 %d개면 칸당 %d자 이내, 휴대폰 좌우 스와이프 방지)" % (c, len(c), ncol, limit))
    # 2026-11-24 민국 확정: "거의 모든 문장마다 줄바꿈한 느낌" → 소제목 문단은 3~4문장, 소제목당 3~5문단.
    # 짧은 꼬리 문단(1~2문장)은 형광펜을 칠하기 애매하므로 앞 문단에 합칩니다.
    def nsent(x):
        return len([s for s in SENT_SPLIT.split(x) if s.strip()])
    shortp, longp, badsec = 0, 0, []
    for sec in ms["sections"]:
        ps = [x for x in sec["paras"] if not x.startswith(TABLE_MARK) and x.replace(" ", "") != READ_MORE.replace(" ", "")]  # 2026-11-25: 맨 끝 '함께 읽으면' 줄은 문단 수·짧은 문단 점검에서 뺀다(서식 단계에서 자동 삽입되는 줄)
        shortp += sum(1 for x in ps if nsent(x) < 3)
        longp += sum(1 for x in ps if nsent(x) > 4)
        if not 3 <= len(ps) <= 5:
            badsec.append("%s %d문단" % (sec["title"][:10], len(ps)))
    if shortp:
        warns.append("소제목 안 1~2문장 문단 %d개 (문단은 3~4문장, 짧은 꼬리 문단은 앞 문단에 합침)" % shortp)
    if longp:
        warns.append("문장이 5개 이상인 문단 %d개 (문단은 3~4문장)" % longp)
    if badsec:
        warns.append("소제목 문단 수가 3~5개 밖: %s" % ", ".join(badsec))
    # ---- AI 티 2단계(2026-11-24 분석): 같은 어미 반복·명사형 종결·출처 머리말 반복·같은 숫자 반복 ----
    run, runs = 0, 0
    for s in sents:
        if s.rstrip().endswith("입니다."):
            run += 1
            if run == 4:
                runs += 1
        else:
            run = 0
    if runs:
        warns.append("'~입니다.'로 끝나는 문장 4개 연속 %d곳 (어미를 섞음: ~합니다·~됩니다·~있습니다·~났습니다)" % runs)
    nom = re.findall(r"(구조|규모|상태|단계|상황|모습|흐름|구간|수준)입니다", text_only)
    if len(nom) > 2:
        warns.append("명사형 종결('~구조/규모/상태/단계입니다') %d곳 (글당 2곳 이내, 동사로 끝냄)" % len(nom))
    for sec in ms["sections"]:
        st = " ".join(x for x in sec["paras"] if not x.startswith(TABLE_MARK))
        n = len(re.findall(r"\d{4}년 \d{1,2}월(?: \d{1,2}일)? ?(?:보도자료|발표|계획|자료)", st))
        if n > 1:
            warns.append("소제목 '%s' 출처 머리말(기관·날짜·발표) %d번 (소제목당 1번, 나머지는 생략)" % (sec["title"][:10], n))
    sec_text = " ".join(x for s in ms["sections"] for x in s["paras"] if not x.startswith(TABLE_MARK))
    nums = re.findall(r"\d[\d,.]*(?:분|%|억 원|만 명|천 명|km|만 대)", sec_text)   # 연도는 일정 글에서 반복이 자연스러워 제외
    rep = sorted({(n, nums.count(n)) for n in nums if nums.count(n) >= 4}, key=lambda z: -z[1])
    if rep:
        warns.append("같은 숫자 4번 이상 반복: %s (핵심 숫자는 2~3번, 소제목 결론끼리 겹치지 않게)" % ", ".join("%s×%d" % r for r in rep[:4]))
    if not ms["tags"]:
        warns.append("태그 줄이 없습니다.")
    return warns, len(body)


def main():
    ap = argparse.ArgumentParser(description="민솜 서식 변환")
    ap.add_argument("manuscript")
    ap.add_argument("spec", nargs="?")
    ap.add_argument("-o", "--out", default="index.html")
    ap.add_argument("--check", action="store_true", help="서식 페이지를 만들지 않고 원고 점검만")
    a = ap.parse_args()

    try:
        ms = parse_manuscript(open(a.manuscript, encoding="utf-8").read())
        spec = parse_spec(open(a.spec, encoding="utf-8").read() if a.spec and not a.check else "")
    except OSError as e:
        die("파일을 열 수 없습니다: %s" % e)

    paras_all = [x for x in ms["intro"] + [y for s in ms["sections"] for y in s["paras"]]]
    warns = []
    if not a.check:
        page, warns = build(ms, spec)
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(page)
    more, nbody = review(ms, paras_all)
    warns += more
    if a.check:
        print("점검: 소제목 %d개 / 원고 분량 약 %d자(태그·유의사항 제외)" % (len(ms["sections"]), nbody))
        if not warns:
            print("통과 - 확인 필요 없음")
    else:
        print("완료: %s (%d자)" % (a.out, len(page)))
        print("소제목 %d개 / 형광펜 %d개 / 사진 %d장 / 원고 분량 약 %d자(태그 제외)"
              % (len(ms["sections"]), len(spec["marks"]), len(spec["photos"]), nbody))
    for w in warns:
        print("확인 필요 - " + w)


if __name__ == "__main__":
    main()
