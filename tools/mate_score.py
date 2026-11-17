# 메이트 176곳의 최근 글 60개 제목을 읽어 부동산 관련도를 채점 (웹검색 0회)
#   python3 -I tools/mate_score.py          # 경기 남부(민솜) → data/mate_scored.json
#   python3 -I tools/mate_score.py --seoul  # 서울 블로그     → data/mate_scored_seoul.json
import json, re, sys, time, html, urllib.request, urllib.parse
UA = "Mozilla/5.0"
SEOUL = "--seoul" in sys.argv
def get(u, ref):
    rq = urllib.request.Request(u, headers={"User-Agent": UA, "Referer": ref})
    with urllib.request.urlopen(rq, timeout=20) as r: return r.read().decode("utf-8", "ignore")
REG_GG = "동탄|화성|수원|영통|광교|용인|기흥|수지|처인|성남|분당|판교|위례|평택|고덕|오산|병점|봉담|향남|안성|의왕|인덕원|과천|경기남부|경기 남부"
# 서울 25개 구 + 정비사업으로 이름난 동네
REG_SEOUL = ("서울|강남|서초|송파|강동|용산|성동|광진|동대문|중랑|성북|강북|도봉|노원|은평|서대문|마포|양천|강서|구로|금천|영등포|동작|관악|종로|중구"
             "|압구정|반포|잠실|목동|여의도|한남|성수|흑석|노량진|신림|상계|중계|방화|가양|대치|개포|청담|이촌|신당|아현|북아현|장위|이문|휘경|미아|길음|신정|창동|수색|증산|불광|갈현|봉천|신길|마곡|왕십리|옥수|금호|행당|자양|화곡|청량리|문래|당산")
REG = REG_SEOUL if SEOUL else REG_GG
RE_ = "부동산|아파트|재건축|재개발|분양|청약|입주|집값|시세|호재|GTX|철도|역세권|노선|신도시|택지|개발|정비|신통|신속통합|모아타운|조합|관리처분|사업시행|토허|토지거래"
mates = json.load(open("data/mate_econ_raw.json"))
out = []
for m in mates:
    bid = m["url"].rstrip("/").split("/")[-1]
    titles = []
    for page in (1, 2):
        u = "https://blog.naver.com/PostTitleListAsync.naver?blogId=%s&viewdate=&currentPage=%d&categoryNo=0&parentCategoryNo=0&countPerPage=30" % (bid, page)
        try:
            d = json.loads(get(u, "https://blog.naver.com/" + bid).replace("\\'", "'"))
            titles += [html.unescape(urllib.parse.unquote_plus(x["title"])) for x in d.get("postList", [])]
        except Exception as e:
            break
        time.sleep(0.4)
    reg = sum(1 for t in titles if re.search(REG, t))
    re_ = sum(1 for t in titles if re.search(RE_, t))
    both = [t for t in titles if re.search(REG, t) and re.search(RE_, t)]
    jb = sum(1 for t in titles if re.search("재건축|재개발|정비|신통|신속통합|모아타운|조합|관리처분|사업시행", t))
    out.append(dict(name=m["name"], url=m["url"], aib=m["aib"], n=len(titles), reg=reg, re=re_, both=len(both), jb=jb,
                    ex=both[:6], first=titles[:3]))
dst = "data/mate_scored_seoul.json" if SEOUL else "data/mate_scored.json"
json.dump(out, open(dst, "w"), ensure_ascii=False, indent=1)
print("done", len(out), "no titles:", sum(1 for o in out if o["n"] == 0), "->", dst)
