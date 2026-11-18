#!/usr/bin/env python3
"""국가법령정보센터(law.go.kr) 법령 조문을 텍스트로 뽑는 도구 (웹검색 0회).

사용법:
  python3 tools/law_fetch.py "재건축초과이익환수에관한법률" 8 11 12 14의2
  python3 tools/law_fetch.py "도시및주거환경정비법" 74 89 --len 2000
  python3 tools/law_fetch.py "노후계획도시정비및지원에관한특별법" --grep 재건축부담금
  python3 tools/law_fetch.py "도시및주거환경정비법" --save /tmp/x.txt   # 본문 전체 저장

- 법령 이름은 띄어쓰기 없이 공식 이름 그대로 씁니다(law.go.kr/법령/<이름> 주소와 같음).
- 조문 번호는 '8', '14의2' 형식. 각 조문은 다음 조문 시작 전까지(최대 --len 글자) 출력합니다.
- 원리: 법령 페이지에서 lsiSeq·efYd를 뽑아 LSW/lsInfoR.do에 POST하면 본문 HTML이 옵니다.
- 연결이 끊기면 최대 3회 다시 시도합니다. 별표(첨부 파일)는 받지 않습니다.
"""
import argparse
import html
import re
import sys
import time
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"
BASE = "https://www.law.go.kr"


def fetch(url, data=None, tries=3):
    """GET(data=None) 또는 POST. 연결 끊김은 3회까지 재시도."""
    body = urllib.parse.urlencode(data).encode() if data else None
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=body, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode("utf-8", errors="ignore")
        except Exception as e:  # 네트워크 오류는 재시도
            last = e
            time.sleep(2 * (i + 1))
    sys.exit(f"[실패] {url} 접속 안 됨: {last}")


def to_text(raw):
    raw = re.sub(r"<script.*?</script>|<style.*?</style>", " ", raw, flags=re.S)
    raw = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(raw)).strip()


def law_text(name):
    page = fetch(f"{BASE}/{urllib.parse.quote('법령')}/{urllib.parse.quote(name)}")
    seq = re.search(r"lsiSeq\s*:\s*'(\d+)", page)
    efyd = re.search(r"efYd\s*:\s*'(\d{8})", page)
    if not seq:
        sys.exit(f"[실패] '{name}' 법령을 찾지 못했습니다. 띄어쓰기 없는 공식 이름인지 확인하세요.")
    data = {"lsiSeq": seq.group(1), "chrClsCd": "010202", "ancYnChk": "0"}
    if efyd:
        data["efYd"] = efyd.group(1)
    text = to_text(fetch(f"{BASE}/LSW/lsInfoR.do", data))
    if len(text) < 1000:
        sys.exit("[실패] 본문이 비어 있습니다(기본정보 조회 실패). 잠시 뒤 다시 시도하세요.")
    head = f"[{name}] lsiSeq={seq.group(1)} 시행일={data.get('efYd', '미상')} 주소={BASE}/LSW/lsInfoP.do?lsiSeq={seq.group(1)}"
    return head, text


def article(text, no, maxlen):
    """'제N조(' 또는 '제N조의M(' 로 시작하는 첫 조문(본문)을 다음 조문 전까지 잘라 반환."""
    m = re.match(r"(\d+)(?:의(\d+))?$", no)
    if not m:
        return f"[형식 오류] {no}"
    label = f"제{m.group(1)}조" + (f"의{m.group(2)}" if m.group(2) else "")
    # 목차가 아닌 본문을 잡기 위해 '제N조(제목) 본문'이 가장 긴 위치를 고름
    hits = [h.start() for h in re.finditer(re.escape(label) + r"\(", text)]
    if not hits:
        return f"===== {label}: 없음"
    best = max(hits, key=lambda s: len(text[s:s + maxlen]))
    seg = text[best:best + maxlen]
    nxt = re.search(r" 제\d+조(?:의\d+)?\(", seg[len(label) + 1:])
    if nxt:
        seg = seg[: len(label) + 1 + nxt.start()]
    return f"===== {seg.strip()}"


def main():
    ap = argparse.ArgumentParser(description="law.go.kr 조문 추출")
    ap.add_argument("name", help="법령 이름(띄어쓰기 없이)")
    ap.add_argument("articles", nargs="*", help="조문 번호(예: 8 14의2)")
    ap.add_argument("--len", type=int, default=1500, help="조문당 최대 글자 수")
    ap.add_argument("--grep", help="본문에서 이 단어 주변 600자를 출력")
    ap.add_argument("--save", help="본문 전체를 이 파일에 저장")
    a = ap.parse_args()

    head, text = law_text(a.name)
    print(head)
    if a.save:
        with open(a.save, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"[저장] {a.save} ({len(text)}자)")
    for no in a.articles:
        print(article(text, no, a.len), "\n")
    if a.grep:
        found = list(re.finditer(re.escape(a.grep), text))
        print(f"[grep] '{a.grep}' {len(found)}건")
        for h in found[:8]:
            print("---", text[max(0, h.start() - 300): h.start() + 300])
    if not (a.articles or a.grep or a.save):
        print("[안내] 조문 번호나 --grep/--save 중 하나를 주세요.")


if __name__ == "__main__":
    main()
