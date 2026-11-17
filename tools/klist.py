#!/usr/bin/env python3
# korea.kr 날짜별 보도자료 목록에서 키워드 제목 찾기
# 사용: python3 -I klist.py 시작일 종료일 키워드정규식 [최대쪽]
import re, sys, html, subprocess
s, e, kw = sys.argv[1:4]
maxp = int(sys.argv[4]) if len(sys.argv) > 4 else 4
for p in range(1, maxp + 1):
    u = f"https://www.korea.kr/briefing/pressReleaseList.do?startDate={s}&endDate={e}&pageIndex={p}"
    try:
        t = subprocess.run(["curl", "-sSL", "--retry", "2", "-m", "40", u], capture_output=True, text=True, errors="ignore").stdout
    except Exception as ex:
        print("err", ex); continue
    found = 0
    for m in re.finditer(r'newsId=(\d+)[^>]*>(.*?)</a>', t, re.S):
        found += 1
        title = html.unescape(re.sub(r'<[^>]+>|\s+', ' ', m.group(2))).strip()
        if re.search(kw, title):
            print(p, m.group(1), title[:110])
    if found == 0:
        break
