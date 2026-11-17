# 메이트 176곳의 최근 글 60개 제목을 읽어 '경기 남부 부동산' 관련도를 채점
import json, re, time, html, urllib.request, urllib.parse
UA = "Mozilla/5.0"
def get(u, ref):
    rq = urllib.request.Request(u, headers={"User-Agent": UA, "Referer": ref})
    with urllib.request.urlopen(rq, timeout=20) as r: return r.read().decode("utf-8", "ignore")
REG = "동탄|화성|수원|영통|광교|용인|기흥|수지|처인|성남|분당|판교|위례|평택|고덕|오산|병점|봉담|향남|안성|의왕|인덕원|과천|경기남부|경기 남부"
RE_ = "부동산|아파트|재건축|재개발|분양|청약|입주|집값|시세|호재|GTX|철도|역세권|노선|신도시|택지|개발|정비"
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
    n = len(titles) or 1
    reg = sum(1 for t in titles if re.search(REG, t))
    re_ = sum(1 for t in titles if re.search(RE_, t))
    both = sum(1 for t in titles if re.search(REG, t) and re.search(RE_, t))
    out.append(dict(name=m["name"], url=m["url"], aib=m["aib"], n=len(titles), reg=reg, re=re_, both=both,
                    ex=[t for t in titles if re.search(REG, t)][:4], first=titles[:3]))
json.dump(out, open("data/mate_scored.json", "w"), ensure_ascii=False, indent=1)
print("done", len(out), "no titles:", sum(1 for o in out if o["n"] == 0))
