#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""민솜 글감 스캔 (웹검색 0회로 수요 신호를 모은다)

하는 일
  1) 블로그에 실제로 올라온 글 제목을 직접 읽어 온다 (글 목록 DB가 밀려 있어도 중복을 막기 위함)
  2) 네이버 검색 자동완성을 씨앗 키워드별로 읽어, 지난번 기록에 없던 새 연관어만 보여 준다
     (새로 뜬 연관어 = 사람들이 요즘 새로 찾기 시작한 말)

실행
  python3 tools/topic_scan.py              # 새 연관어 + 최근 글 제목 30개
  python3 tools/topic_scan.py --titles 150 # 최근 글 제목을 150개까지
  python3 tools/topic_scan.py --check "오산용인고속도로" "분양전환"   # 이미 쓴 주제인지 제목에서 찾기
  python3 tools/topic_scan.py --kw "동탄 트램" "인덕원선"   # 원고용: 그 키워드의 네이버 자동완성 연관어만 출력
  python3 tools/topic_scan.py --seoul [--check …]          # 서울 블로그: 서울 씨앗 키워드·서울 블로그 제목·data/ac_snapshot_seoul.json
기록 파일: data/ac_snapshot.json (실행할 때마다 갱신, 사진과 같은 push에 포함)
"""
import argparse
import html
import json
import os
import sys
import urllib.parse
import urllib.request

BLOG_ID = "minsoaa"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"
HERE = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(HERE, "..", "data", "ac_snapshot.json")

SEEDS = [
    # 동탄·화성
    "동탄", "동탄역", "동탄 아파트", "동탄 집값", "동탄 분양", "동탄 트램", "병점", "봉담", "화성 반도체",
    # 수원·용인·성남
    "광교", "영통", "수원 재건축", "수원 아파트", "수지 재건축", "용인 아파트", "용인 플랫폼시티", "기흥",
    "분당 재건축", "성남 재개발", "판교", "위례", "과천",
    # 평택·오산
    "평택 고덕", "평택 지제역", "오산 세교",
    # 철도·도로
    "GTX-A", "GTX-C", "신분당선 연장", "인덕원선", "분당선 연장", "국가철도망", "경기남부", "지하고속도로",
    # 반도체
    "용인 반도체", "삼성전자 평택", "SK하이닉스 용인", "반도체 성과급",
    # 제도
    "토허제", "재건축 분담금", "청약 일정",
]


# 서울 블로그 (rules/seoul.md 6-10). 아이디는 민국이 알려 주면 여기 한 곳만 채웁니다.
SEOUL_BLOG_ID = ""
SEOUL_SEEDS = [
    # 정비사업 (재건축·재개발 묶음 키워드)
    "서울 재개발", "서울 재건축", "신속통합기획", "모아타운", "정비구역 지정", "관리처분인가", "사업시행인가", "재건축 분담금",
    "목동 재건축", "상계주공 재건축", "여의도 재건축", "압구정 재건축", "잠실 재건축", "개포 재건축",
    "노량진 재개발", "흑석 재개발", "한남 재개발", "성수 전략정비구역", "북아현 재개발", "장위 재개발", "신림 재개발", "상도 재개발",
    "이문 휘경 재개발", "청량리 재개발", "마천 재개발", "미아 재개발", "봉천 재개발", "수색 증산 재개발",
    # 서울 교통
    "서울 경전철", "서부선", "강북횡단선", "면목선", "목동선", "위례신사선", "신림선 연장", "동북선",
    "GTX-B", "GTX-C 서울", "철도 지하화", "경부선 지하화", "동부간선 지하화", "서울 도시철도망",
    # 규제·거래
    "토지거래허가구역 서울", "조합원 지위 양도", "재초환", "서울 아파트 거래량",
]


def get(url, referer=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **({"Referer": referer} if referer else {})})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "ignore")


def my_titles(limit):
    out = []
    if not BLOG_ID:
        return out
    page = 1
    while len(out) < limit and page <= 10:
        url = ("https://blog.naver.com/PostTitleListAsync.naver?blogId=%s&viewdate=&currentPage=%d"
               "&categoryNo=0&parentCategoryNo=0&countPerPage=30" % (BLOG_ID, page))
        try:
            d = json.loads(get(url, "https://blog.naver.com/" + BLOG_ID).replace("\\'", "'"))
        except Exception as e:
            print("글 목록을 읽지 못했습니다(%d쪽): %s" % (page, e))
            break
        posts = d.get("postList", [])
        if not posts:
            break
        for x in posts:
            out.append((x.get("addDate", "").strip(), html.unescape(urllib.parse.unquote_plus(x["title"]))))
        page += 1
    return out[:limit]


def autocomplete(q):
    url = ("https://ac.search.naver.com/nx/ac?q=%s&con=1&frm=nv&ans=2&r_format=json&r_enc=UTF-8"
           "&r_unicode=0&t_koreng=1&run=2&rev=4&q_enc=UTF-8&st=100" % urllib.parse.quote(q))
    try:
        d = json.loads(get(url))
        return [x[0] for x in d["items"][0]]
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--titles", type=int, default=30)
    ap.add_argument("--check", nargs="*")
    ap.add_argument("--kw", nargs="*")
    ap.add_argument("--seoul", action="store_true", help="서울 블로그 모드")
    a = ap.parse_args()
    global BLOG_ID, SEEDS, SNAP
    if a.seoul:
        SEEDS, SNAP = SEOUL_SEEDS, os.path.join(HERE, "..", "data", "ac_snapshot_seoul.json")
        BLOG_ID = SEOUL_BLOG_ID
        if not BLOG_ID and not a.kw:
            print("※ 서울 블로그 아이디가 아직 없습니다(tools/topic_scan.py의 SEOUL_BLOG_ID). 제목 중복 확인은 건너뜁니다.")

    if a.kw:
        for kw in a.kw:
            items = autocomplete(kw)
            print("[%s] %s" % (kw, ", ".join(items) if items else "연관어 없음(또는 읽기 실패)"))
        return

    if a.check:
        titles = my_titles(300)
        for kw in a.check:
            hits = [t for _, t in titles if kw.replace(" ", "") in t.replace(" ", "")]
            print("[%s] %s" % (kw, "이미 쓴 글 %d건" % len(hits) if hits else "쓴 적 없음"))
            for t in hits[:5]:
                print("   - " + t[:70])
        return

    old = {}
    if os.path.exists(SNAP):
        old = json.load(open(SNAP, encoding="utf-8"))
    new, fails = {}, 0
    print("== 새로 뜬 연관 검색어 (지난 기록 대비) ==")
    for s in SEEDS:
        items = autocomplete(s)
        if items is None:
            fails += 1
            new[s] = old.get(s, [])
            continue
        new[s] = items
        fresh = [i for i in items if i not in old.get(s, [])]
        if fresh and s in old:
            print("%s → %s" % (s, ", ".join(fresh)))
    if not old:
        print("(첫 실행이라 기준 기록만 저장했습니다. 다음 실행부터 새 연관어가 표시됩니다.)")
    if fails:
        print("읽지 못한 키워드 %d개(기존 기록 유지)" % fails)
    os.makedirs(os.path.dirname(SNAP), exist_ok=True)
    json.dump(new, open(SNAP, "w", encoding="utf-8"), ensure_ascii=False, indent=0)

    print("\n== 최근 올린 글 %d개 (중복 확인용) ==" % a.titles)
    for d, t in my_titles(a.titles):
        print("%s | %s" % (d[:12], t[:64]))


if __name__ == "__main__":
    main()
