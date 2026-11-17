#!/usr/bin/env python3
"""외부 글감 수집기 (카페·유튜브·한국경제·경기일보·국토부·블로그) — 웹검색 0회.

실행:  python3 tools/source_scan.py            # 최근 4일(오늘 포함), 기본 몫으로 출력
       python3 tools/source_scan.py --days 3   # 기간 변경
       python3 tools/source_scan.py --all      # 몫 제한 없이 출처별 상위 15개
       python3 tools/source_scan.py --seoul    # 서울 블로그용(data/sources_seoul.tsv, 서울 지명·서울 몫, rules/seoul.md 6-10)
필요 허용 주소: naver.me, apis.naver.com, m.blog.naver.com, www.youtube.com, www.hankyung.com, www.kyeonggi.com, www.korea.kr
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
EXCLUDE = re.compile(r"청약|분양|당첨|미달|줍줍|모집공고|가입인사|등업|광고|홍보|직거래|매물|대출|대통령|정치|국힘|민주당|한동훈|체포|불법촬영|성범죄|살인|사망|폭행|경찰|장관동정")
SKIP_MENU = re.compile(r"가입|등업|광고|홍보|실거래|직거래|매물|정치|공지|출석")
# 한국경제 랭킹은 연예·사회가 섞여 있으므로 부동산·지역 낱말이 있어야 통과
HK_KEEP = re.compile(r"아파트|집값|재건축|재개발|분담금|부동산|토허|GTX|철도|노선|신도시|반도체|" + REGION_TOP.pattern + "|" + REGION_OK.pattern)


def get(url, referer=None, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ko-KR",
                                               **({"Referer": referer} if referer else {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")


# ── 서울 모드(--seoul) 낱말: main()에서 위 전역값을 바꿔 끼운다 ──
SEOUL_TOP = re.compile(r"강남|서초|송파|강동|용산|성동|광진|동대문|중랑|성북|강북|도봉|노원|은평|서대문|마포|양천|강서|구로|금천|영등포|동작|관악|종로"
                       r"|압구정|반포|잠실|목동|여의도|한남|성수|흑석|노량진|신림|상계|중계|대치|개포|이촌|신당|아현|장위|이문|휘경|미아|길음|창동|수색|증산|불광|봉천|신길|마곡|왕십리|청량리|자양|화곡|방화|상도|공덕|문래|당산")
SEOUL_OK = re.compile(r"서울|강북|강남권|한강")
JB = re.compile(r"재건축|재개발|정비|신통|신속통합|모아타운|모아주택|가로주택|조합|관리처분|사업시행|통합심의|시공사|이주|철거|분담금|비례율|구역")
RULE = re.compile(r"토허|토지거래|허가구역|투기과열|규제|지위 ?양도|대출|거래량|실거래|신고가|재초환|전매")
SEOUL_EXCLUDE = re.compile(r"청약|당첨|미달|줍줍|모집공고|모델하우스|가입인사|등업|광고|홍보|직거래|매물|대통령|정치|국힘|민주당|체포|성범죄|살인|사망|폭행|경찰|장관동정|비대위|조합장 ?해임")


def load_sources(fname="data/sources.tsv"):
    rows = []
    for line in (ROOT / fname).read_text(encoding="utf-8").splitlines()[1:]:
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


def kyeonggi_items(src):
    """경기일보: 많이 본 기사(컴포넌트 34, 5개) + 지역 주요 기사(41) 중 지역·부동산 낱말이 있는 것."""
    out = []
    for comp, label in (("34", "많이 본"), ("41", "지역 주요")):
        t = get(f"https://www.kyeonggi.com/wps/engine/rest/{comp}?type=COMPONENT", "https://www.kyeonggi.com/")
        rows = re.findall(r'<a[^>]*href="([^"]*article/\d+)"[^>]*>(.*?)</a>', t, re.S)
        rank = 0
        for url, b in rows:
            title = html.unescape(re.sub("<[^>]+>", "", b)).strip()
            if len(title) < 9:
                continue
            rank += 1
            if comp == "34" and title.startswith(str(rank)):
                title = title[len(str(rank)):].strip()  # 앞에 붙은 순위 숫자 떼기
            if comp == "41" and not HK_KEEP.search(title):
                continue
            out.append({"src": src["name"], "title": title, "menu": f"{label} {rank}",
                        "views": (11 - rank) * (3 if comp == "34" else 1), "comments": 0, "ts": time.time(),
                        "url": url if url.startswith("http") else "https://www.kyeonggi.com" + url})
    return out


def molit_items(src, cutoff_ms):
    """정책브리핑 국토교통부 보도자료(국토부 사이트 대신). 조회수 없음 → 낱말로만 거름."""
    out = []
    for page in range(1, 6):
        h = get("https://www.korea.kr/briefing/pressReleaseList.do?repCodeType=%EC%A0%95%EB%B6%80%EB%B6%80%EC%B2%98"
                f"&repCode=A00006&pageIndex={page}")
        R = re.findall(r'pressReleaseView\.do\?newsId=(\d+)[^>]*>\s*<span class="text">\s*<strong>(.*?)</strong>'
                       r'.*?<span class="source">\s*<span>([\d.\-]+)</span>', h, re.S)
        for nid, t, d in R:
            ts = dt.datetime.strptime(d.replace(".", "-"), "%Y-%m-%d").replace(tzinfo=KST).timestamp()
            title = html.unescape(re.sub("<[^>]+>", "", t)).strip()
            if ts * 1000 >= cutoff_ms and (HK_KEEP.search(title) or RAIL.search(title)):
                out.append({"src": src["name"], "title": title, "menu": "보도자료", "views": 10, "comments": 0,
                            "ts": ts, "url": f"https://www.korea.kr/briefing/pressReleaseView.do?newsId={nid}"})
        if not R or ts * 1000 < cutoff_ms:
            break
    return out


# 블로그: 맛집·제품 후기·광고 글 제외 (제목 기준)
BLOG_SKIP = re.compile(r"후기|맛집|추천|체험|협찬|제공받|내돈내산|리뷰|광고|원고료|공구|이벤트|언박싱|카페투어|일상|주말|여행|육아일기")


def blog_items(src, cutoff_ms):
    """블로그 최근 30개 글. 조회수는 대부분 숨김 → 댓글 수로 판단.
    최근 30개 평균 댓글의 2배 이상(최소 1개)인 cutoff 이후 글 중 배수가 가장 큰 1개만 돌려줌."""
    bid = src["id"]
    d = json.loads(get(f"https://m.blog.naver.com/api/blogs/{bid}/post-list?categoryNo=0&itemCount=30&page=1",
                       f"https://m.blog.naver.com/{bid}"))
    posts = [p for p in d["result"]["items"] if not p.get("notOpen") and not p.get("postBlocked")]
    if not posts:
        return []
    avg = statistics.mean([p.get("commentCnt") or 0 for p in posts])
    best = None
    for p in posts:
        c = p.get("commentCnt") or 0
        title = html.unescape(p.get("titleWithInspectMessage") or "").strip()
        if (p["addDate"] < cutoff_ms or c < 1 or c < 2 * avg or p.get("marketPost") or p.get("product")
                or BLOG_SKIP.search(title) or EXCLUDE.search(title)
                or not (HK_KEEP.search(title) or RAIL.search(title))):  # 부동산·철도 글만
            continue
        ratio = c / max(avg, 0.5)
        if not best or ratio > best["ratio"]:
            best = {"src": src["name"], "title": title, "menu": f"{ratio:.1f}배(평균{avg:.1f})",
                    "views": 0, "comments": c, "ratio": ratio, "ts": p["addDate"] / 1000,
                    "url": f"https://m.blog.naver.com/{bid}/{p['logNo']}"}
    time.sleep(0.3)  # 블로그 서버 부담 줄이기
    return [best] if best else []


def score(items):
    """점수 100점: 반응 배수 40 + 지역 25 + 겹침 25 + 댓글 비율 10. 제외 낱말은 0점 처리."""
    by_src = {}
    for it in items:
        by_src.setdefault(it["src"], []).append(it)
    for L in by_src.values():
        med = statistics.median([max(1, x["views"]) for x in L])
        for x in L:
            # 블로그는 조회수 대신 '자기 평균 댓글 대비 배수'를 반응 배수로 씀(2배=20점, 4배 이상=40점)
            x["rel"] = x["ratio"] if "ratio" in x else x["views"] / med
    # 겹침: 지역·철도 핵심 낱말이 2개 이상 출처에서 등장
    tok = re.compile(REGION_TOP.pattern + "|" + REGION_OK.pattern + r"|GTX-?[A-F]|\d호선|[가-힣]{2,4}선(?![가-힣])|트램|터널|재건축")
    seen = {}
    for x in items:
        for w in set(tok.findall(x["title"])):
            seen.setdefault(w, set()).add(x["src"])
    for x in items:
        t = x["title"]
        tr = t + " " + x.get("menu", "") if SEOUL_MODE else t   # 서울: 구 게시판 이름도 지역으로 침
        reg = 25 if REGION_TOP.search(tr) else 15 if REGION_OK.search(t) else 0
        ov = 25 if any(len(seen[w]) >= 2 for w in set(tok.findall(t)) if w not in ("반도체", "서울", "한강")) else 0
        cr = 0 if "ratio" in x else min(10, x["comments"] / max(1, x["views"]) * 500)
        x["score"] = 0 if EXCLUDE.search(t) else round(min(40, x["rel"] * 10) + reg + ov + cr)
        if SEOUL_MODE:   # 서울: 정비 / 교통 / 규제거래 / 동네(그 밖)
            x["kind"] = "정비" if JB.search(t) else "철도" if RAIL.search(t) else "규제거래" if RULE.search(t) else "지역"
        else:
            x["kind"] = "철도" if RAIL.search(t) else "새소식" if NEWS.search(t) else "지역"
    return items


# 하루 몫 (민국과 맞춰 가는 값 — 바꾸면 여기만 고칩니다)
QUOTA = [("동탄 카페", lambda x: x["group"] == "dongtan", 3),
         ("부동산스터디·철도", lambda x: x["group"] == "study" and x["kind"] == "철도", 2),
         ("부동산스터디·새소식", lambda x: x["group"] == "study" and x["kind"] == "새소식", 2),
         ("부동산스터디·지역", lambda x: x["group"] == "study" and x["kind"] == "지역", 3),
         ("유튜브(5만+)", lambda x: x["group"] == "youtube", 4),
         ("한국경제 랭킹", lambda x: x["group"] == "news", 2),
         ("경기일보", lambda x: x["group"] == "kyeonggi", 2),
         ("국토부 보도자료(정책브리핑)", lambda x: x["group"] == "molit", 2),
         ("블로그", lambda x: x["group"] == "blog", 5)]  # 블로그마다 최대 1개(blog_items에서 보장)


# 서울 하루 몫 (rules/seoul.md 6-10 — 바꾸면 여기만 고칩니다). 카페는 부동산스터디만.
QUOTA_SEOUL = [("부동산스터디·정비사업", lambda x: x["group"] == "study" and x["kind"] == "정비", 5),
               ("부동산스터디·서울교통", lambda x: x["group"] == "study" and x["kind"] == "철도", 3),
               ("부동산스터디·동네(구 게시판)", lambda x: x["group"] == "study" and x["kind"] == "지역", 3),
               ("부동산스터디·규제거래", lambda x: x["group"] == "study" and x["kind"] == "규제거래", 2),
               ("유튜브(5만+)", lambda x: x["group"] == "youtube", 3),
               ("한국경제 랭킹", lambda x: x["group"] == "news", 2),
               ("국토부 보도자료(정책브리핑)", lambda x: x["group"] == "molit", 1),
               ("서울 메이트 블로그", lambda x: x["group"] == "blog", 5)]
SEOUL_MODE = False


def main():
    global REGION_TOP, REGION_OK, HK_KEEP, EXCLUDE, QUOTA, SEOUL_MODE
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=3, help="오늘로부터 며칠 전 0시까지 (기본 3 → 4일치)")
    ap.add_argument("--min-views", type=int, default=50000, help="유튜브 최소 조회수")
    ap.add_argument("--all", action="store_true", help="몫 제한 없이 출처별 상위 15개")
    ap.add_argument("--seoul", action="store_true", help="서울 블로그용 출처·지명·몫")
    a = ap.parse_args()
    if a.seoul:
        SEOUL_MODE = True
        REGION_TOP, REGION_OK, EXCLUDE, QUOTA = SEOUL_TOP, SEOUL_OK, SEOUL_EXCLUDE, QUOTA_SEOUL
        HK_KEEP = re.compile(r"아파트|집값|재건축|재개발|분담금|부동산|토허|GTX|철도|노선|지하철|경전철|지하화|" + JB.pattern + "|" + SEOUL_TOP.pattern + "|" + SEOUL_OK.pattern)
    today = dt.datetime.now(KST).replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff_ms = (today - dt.timedelta(days=a.days)).timestamp() * 1000

    items, fails = [], []
    for s in load_sources("data/sources_seoul.tsv" if a.seoul else "data/sources.tsv"):
        try:
            if s["type"] == "cafe":
                got = cafe_items(s, cutoff_ms)
                grp = "study" if s["menus"] else "dongtan"
            elif s["type"] == "youtube":
                got, grp = youtube_items(s, cutoff_ms, a.min_views), "youtube"
            elif s["type"] == "hankyung":
                got, grp = hankyung_items(s), "news"
            elif s["type"] == "kyeonggi":
                got, grp = kyeonggi_items(s), "kyeonggi"
            elif s["type"] == "blog":
                got, grp = blog_items(s, cutoff_ms), "blog"
            elif s["type"] == "molit":
                got, grp = molit_items(s, cutoff_ms), "molit"
            else:
                continue
            for x in got:
                x["group"] = grp
            items += got
        except Exception as e:  # 한 출처가 막혀도 나머지는 계속
            fails.append(f"{s['name']}: {type(e).__name__} {str(e)[:80]}")

    score(items)
    print(f"# {'서울 ' if a.seoul else ''}외부 글감 수집 {dt.datetime.now(KST):%Y-%m-%d %H:%M} (기준: {today - dt.timedelta(days=a.days):%m-%d} 0시 이후, {len(items)}건)")
    picked = set()
    for label, cond, n in QUOTA:
        L = sorted([x for x in items if cond(x) and x["score"] > 0], key=lambda x: -x["score"])[: 15 if a.all else n]
        print(f"\n## {label} ({len(L)})")
        print("점수\t조회\t댓글\t날짜\t출처/게시판\t제목")
        for x in L:
            picked.add(id(x))
            d = dt.datetime.fromtimestamp(x["ts"], KST)
            print(f"{x['score']}\t{'-' if x['group'] == 'blog' else x['views']}\t{x['comments']}\t{d:%m-%d}\t{x['src']}/{x['menu'][:10]}\t{x['title'][:50]}\t{x['url']}")
    if fails:
        print("\n## 수집 실패(허용 주소·사이트 구조 확인 필요)")
        for f in fails:
            print("-", f)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
