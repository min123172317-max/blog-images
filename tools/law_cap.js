// 법령 조문 캡처 (2026-11-18, 분당 재건축 분담금 글에서 확인한 방식)
// law.go.kr 조문(div.pgroup)을 폭 600px로 다시 흘려(글자 내용은 그대로) 고해상도로 캡처합니다.
// 긴 조문은 원래 폭이 1,600px를 넘어 1080으로 줄이면 글자가 안 읽히므로 이 도구를 씁니다.
//
// 실행:
//   node tools/law_cap.js "법령명" "제8조(" 출력.png ["③"]
//   - 네 번째 값(멈출 문단 접두어)을 주면 그 문단 바로 위에서 자를 위치를 'CUT_PX'로 알려 줍니다.
//   - 다음 단계: python3 -I tools/cap.py 출력.png 최종.jpg 55 60 1200 CUT_PX 24
//     (왼쪽 55px·위 60px를 빼면 체크박스와 '판 연 규 생활법령' 아이콘 줄이 잘립니다)
//   - 사이트가 가끔 '조문 못 찾음'으로 끝나면 한 번만 다시 실행합니다.
const { chromium } = require('playwright');

(async () => {
  const [lawNm, jo, out, stop] = process.argv.slice(2);
  if (!lawNm || !jo || !out) {
    console.error('사용법: node tools/law_cap.js "법령명" "제8조(" 출력.png ["③"]');
    process.exit(1);
  }
  const b = await chromium.launch();
  try {
    // 화면 높이가 조문보다 낮으면 빈 그림이 찍히므로 높게 잡습니다.
    const p = await b.newPage({ viewport: { width: 700, height: 4000 }, deviceScaleFactor: 2 });
    await p.goto('https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=0&lsNm=' + encodeURIComponent(lawNm),
      { waitUntil: 'networkidle', timeout: 90000 });
    await p.waitForTimeout(3000);
    for (const f of p.frames()) {
      for (const h of await f.$$('div.pgroup')) {
        const t = (await h.innerText()).trim();
        if (!t.startsWith(jo)) continue;
        await f.addStyleTag({ content:
          '.law-cap{width:600px!important;max-width:600px!important;overflow:visible!important}' +
          '.law-cap *{white-space:normal!important;max-width:600px!important;word-break:keep-all}' });
        await h.evaluate(n => n.classList.add('law-cap'));
        await p.waitForTimeout(800);
        await h.scrollIntoViewIfNeeded();
        const r = await h.evaluate((n, s) => {
          const top = n.getBoundingClientRect().top;
          let cut = null;
          if (s) for (const c of n.querySelectorAll('p, div, span')) {
            if (c.innerText && c.innerText.trim().startsWith(s)) { cut = c.getBoundingClientRect().top - top; break; }
          }
          return { h: n.getBoundingClientRect().height, cut };
        }, stop || '');
        await h.screenshot({ path: out });
        console.log(t.slice(0, 300));
        if (stop) console.log(r.cut === null ? '멈출 문단 못 찾음(전체 사용)' : 'CUT_PX ' + Math.round(r.cut * 2));
        return;
      }
    }
    console.error('조문 못 찾음');
    process.exitCode = 2;
  } catch (e) {
    console.error('오류', e.message);
    process.exitCode = 1;
  } finally {
    await b.close();
  }
})();
