#!/usr/bin/env python3
"""외부 글감 수집기 (카페·유튜브·한국경제) — 웹검색 0회.

실행:  python3 tools/source_scan.py            # 최근 4일(오늘 포함), 기본 몫으로 출력
       python3 tools/source_scan.py --days 3   # 기간 변경
       python3 tools/source_scan.py --all      # 몫 제한 없이 출처별 상위 15개
필요 허용 주소: naver.me, apis.naver.com, www.youtube.com, www.hankyung.com
출처 목록은 data/sources.tsv (type, name, id, menus) 에서 읽습니다.
"""
import argparse, datetime as dt, html, json, re, statistics, sys, time
import urllib.request, xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"
KST = dt.timezone(dt.timedelta(hours=9))

# ── 분류 낱말 (rules/topic.md 2-3·2-8 기준) ──
REGION_TOP = re.compile(r"동탄|화성|병점|진안|봉담|향남")
REGION_OK = re.compile(r"수원|광교|영통|용인|수지|기흥|처인|성남|분당|판교|위례|평택|고덕|반도체")
RAIL = re.compile(r"GTX|철도|노선|연장|개통|KTX|SRT|트램|지하철|\d호선|[가-힣]{1,4}선(?![가-힣])|정차|역세권|착공")
NEWS = re.compile(r"속보|발표|확정|승인|인가|선정|협약|착공|고시|지정|통과|완화|단독")
EXCLUDE = re.compile(r"청약|분양|당첨|미달|줍줍|모집공고|가입인사|등업|광고|홍보|직거래|매물|대출|대통령|정치|국힘|민주당|한동훈|체포|불법촬영|성범죄|살인|사망|폭행|경찰")
SKIP_MENU = re.compile(r"가입|등업|광고|홍보|실거래|직거래|매물|정치|공지|출석")
# 한국경제 랭킹은 연예·사회가 섞여 있으므로 부동산·지역 낱말이 있어야 통과
HK_KEEP = re.compile(r"아파트|집값|재건축|재개발|분담금|부동산|토허|GTX|철도|노선|신도시|반도체|" + REGION_TOP.pattern + "|" + REGION_OK.pattern)


def get(url, referer=None, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ko-KR",
                                               **({"Referer": referer} if referer else {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")


def load_sources():
    rows = []
    for line in (ROOT / "data/sources.tsv").read_text(encoding="utf-8").splitlines()[1:]:
        if line.strip() and not line.startswith("#"):
            t, name, sid, menus = (line.split("\t") + ["", "", "", ""])[:4]
            rows.append({"type": t, "name": name, "id": sid, "menus": [m for m in menus.split(",") if m]})
    return rows


def cafe_items(src, cutoff_ms):
    """카페 글 목록. menus가 있으면 그 게시판만, 없으면 전체글을 cutoff까지 넘김."""
    ref = "https://m.cafe.naver.com/"
    base = ("https://apis.naver.com/cafe-web/cafe2/ArticleListV2dot1.json?search.clubid={}"
            "&search.queryType=lastArticle&search.perPage=50&search.page={}").format(src["id"], "{}")
    targets = [base + f"&search.menuid={m}" for m in src["menus"]] or [base]
    out = {}
    for tpl in targets:
        for page in range(1, 21):  # 게시판당 최대 1,000개
            L = json.loads(get(tpl.format(page), ref))["message"]["result"]["articleList"]
            for a in L:
                if a["writeDateTimestamp"] < cutoff_ms or SKIP_MENU.search(a.get("menuName", "")):
                    continue
                out[a["articleId"]] = {
                    "src": src["name"], "title": html.unescape(a["subject"]), "menu": html.unescape(a.get("menuName", "")),
                    "views": a.get("readCount") or 0, "comments": a.get("commentCount") or 0,
                    "ts": a["writeDateTimestamp"] / 1000,
                    "url": f"https://m.cafe.naver.com/ca-fe/web/cafes/{src['id']}/articles/{a['articleId']}"}
            if not L or L[-1]["writeDateTimestamp"] < cutoff_ms:
                break
            time.sleep(0.3)  # 카페 서버 부담 줄이기
    return list(out.values())


def youtube_items(src, cutoff_ms, min_views):
    ns = {"a": "http://www.w3.org/2005/Atom", "m": "http://search.yahoo.com/mrss/"}
    root = ET.fromstring(get(f"https://www.youtube.com/feeds/videos.xml?channel_id={src['id']}"))
    out = []
    for e in root.findall("a:entry", ns):
        ts = dt.datetime.fromisoformat(e.find("a:published", ns).text).timestamp()
        st = e.find("m:group/m:community/m:statistics", ns)
        views = int(st.get("views")) if st is not None else 0
        if ts * 1000 < cutoff_ms or views < min_views:
            continue
        title = e.find("a:title", ns).text
        out.append({"src": src["name"], "title": title, "menu": "쇼츠" if ("#shorts" in title or "/shorts/" in e.find("a:link", ns).get("href")) else "영상",
                    "views": views, "comments": 0, "ts": ts, "url": e.find("a:link", ns).get("href")})
    return out


def hankyung_items(src):
    h = get("https://www.hankyung.com/ranking")
    out = []
    for rank, (url, t) in enumerate(re.findall(r'class="news-tit"[^>]*>\s*<a href="([^"]+)"[^>]*>(.*?)</a>', h, re.S), 1):
        title = html.unescape(re.sub("<[^>]+>", "", t)).strip()
        if HK_KEEP.search(title):
            # 조회수 숫자가 없으므로 순위를 가짜 조회수로 환산(1위=30, 30위=1)
            out.append({"src": src["name"], "title": title, "menu": f"랭킹 {rank}위",
                        "views": 31 - rank, "comments": 0, "ts": time.time(), "url": url})
    return out


def score(items):
    """점수 100점: 반응 배수 40 + 지역 25 + 겹침 25 + 댓글 비율 10. 제외 낱말은 0점 처리."""
    by_src = {}
    for it in items:
        by_src.setdefault(it["src"], []).append(it)
    for L in by_src.values():
        med = statistics.median([max(1, x["views"]) for x in L])
        for x in L:
            x["rel"] = x["views"] / med
    # 겹침: 지역·철도 핵심 낱말이 2개 이상 출처에서 등장
    tok = re.compile(REGION_TOP.pattern + "|" + REGION_OK.pattern + r"|GTX-?[A-F]|\d호선|[가-힣]{2,4}선(?![가-힣])|트램|터널|재건축")
    seen = {}
    for x in items:
        for w in set(tok.findall(x["title"])):
            seen.setdefault(w, set()).add(x["src"])
    for x in items:
        t = x["title"]
        reg = 25 if REGION_TOP.search(t) else 15 if REGION_OK.search(t) else 0
        ov = 25 if any(len(seen[w]) >= 2 for w in set(tok.findall(t)) if w not in ("반도체",)) else 0
        cr = min(10, x["comments"] / max(1, x["views"]) * 500)
        x["score"] = 0 if EXCLUDE.search(t) else round(min(40, x["rel"] * 10) + reg + ov + cr)
        x["kind"] = "철도" if RAIL.search(t) else "새소식" if NEWS.search(t) else "지역"
    return items


# 하루 몫 (민국과 맞춰 가는 값 — 바꾸면 여기만 고칩니다)
QUOTA = [("동탄 카페", lambda x: x["group"] == "dongtan", 3),
         ("부동산스터디·철도", lambda x: x["group"] == "study" and x["kind"] == "철도", 2),
         ("부동산스터디·새소식", lambda x: x["group"] == "study" and x["kind"] == "새소식", 2),
         ("부동산스터디·지역", lambda x: x["group"] == "study" and x["kind"] == "지역", 3),
         ("유튜브(5만+)", lambda x: x["group"] == "youtube", 4),
         ("한국경제 랭킹", lambda x: x["group"] == "news", 2)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=3, help="오늘로부터 며칠 전 0시까지 (기본 3 → 4일치)")
    ap.add_argument("--min-views", type=int, default=50000, help="유튜브 최소 조회수")
    ap.add_argument("--all", action="store_true", help="몫 제한 없이 출처별 상위 15개")
    a = ap.parse_args()
    today = dt.datetime.now(KST).replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff_ms = (today - dt.timedelta(days=a.days)).timestamp() * 1000

    items, fails = [], []
    for s in load_sources():
        try:
            if s["type"] == "cafe":
                got = cafe_items(s, cutoff_ms)
                grp = "study" if s["menus"] else "dongtan"
            elif s["type"] == "youtube":
                got, grp = youtube_items(s, cutoff_ms, a.min_views), "youtube"
            elif s["type"] == "hankyung":
                got, grp = hankyung_items(s), "news"
            else:
                continue
            for x in got:
                x["group"] = grp
            items += got
        except Exception as e:  # 한 출처가 막혀도 나머지는 계속
            fails.append(f"{s['name']}: {type(e).__name__} {str(e)[:80]}")

    score(items)
    print(f"# 외부 글감 수집 {dt.datetime.now(KST):%Y-%m-%d %H:%M} (기준: {today - dt.timedelta(days=a.days):%m-%d} 0시 이후, {len(items)}건)")
    picked = set()
    for label, cond, n in QUOTA:
        L = sorted([x for x in items if cond(x) and x["score"] > 0], key=lambda x: -x["score"])[: 15 if a.all else n]
        print(f"\n## {label} ({len(L)})")
        print("점수\t조회\t댓글\t날짜\t출처/게시판\t제목")
        for x in L:
            picked.add(id(x))
            d = dt.datetime.fromtimestamp(x["ts"], KST)
            print(f"{x['score']}\t{x['views']}\t{x['comments']}\t{d:%m-%d}\t{x['src']}/{x['menu'][:10]}\t{x['title'][:50]}\t{x['url']}")
    if fails:
        print("\n## 수집 실패(허용 주소·사이트 구조 확인 필요)")
        for f in fails:
            print("-", f)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
