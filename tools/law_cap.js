// 법령 조문 캡처 (2026-11-18, 분당 재건축 분담금 글에서 확인한 방식)
// law.go.kr 조문(div.pgroup)을 폭 600px로 다시 흘려(글자 내용은 그대로) 고해상도로 캡처합니다.
// 긴 조문은 원래 폭이 1,600px를 넘어 1080으로 줄이면 글자가 안 읽히므로 이 도구를 씁니다.
//
// 실행:
//   node tools/law_cap.js "법령명" "제8조(" 출력.png ["③"] ["②"]
//   - 네 번째 값(멈출 문단 접두어)을 주면 그 문단 바로 위에서 자를 위치를 'CUT_PX'로 알려 줍니다.
//   - 다섯 번째 값(시작 문단 접두어)을 주면 그 문단 바로 위 위치를 'START_PX'로 알려 줍니다(항 하나만 캡처할 때).
//   - 재는 위치가 실제 그림보다 약 40px(2배 해상도 기준) 아래로 나와 보정값을 빼고 출력합니다
//     (2026-11-18 목동 글: ②항 1100→1062, ③항 2273→2232로 직접 고쳐 맞춤).
//   - 다음 단계: python3 -I tools/cap.py 출력.png 최종.jpg 55 60 1200 CUT_PX 24
//     (항 하나만이면 60 대신 START_PX)
//     (왼쪽 55px·위 60px를 빼면 체크박스와 '판 연 규 생활법령' 아이콘 줄이 잘립니다)
//   - 사이트가 가끔 '조문 못 찾음'으로 끝나면 한 번만 다시 실행합니다.
const { chromium } = require('playwright');

(async () => {
  const [lawNm, jo, out, stop, start] = process.argv.slice(2);
  const FIX = 40; // 측정 위치 보정(px, 2배 해상도 기준)
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
        const r = await h.evaluate((n, [s, st]) => {
          const top = n.getBoundingClientRect().top;
          const find = (pre) => {
            if (!pre) return null;
            for (const c of n.querySelectorAll('p, div, span')) {
              if (c.innerText && c.innerText.trim().startsWith(pre)) return c.getBoundingClientRect().top - top;
            }
            return null;
          };
          return { h: n.getBoundingClientRect().height, cut: find(s), start: find(st) };
        }, [stop || '', start || '']);
        await h.screenshot({ path: out });
        console.log(t.slice(0, 300));
        if (start) console.log(r.start === null ? '시작 문단 못 찾음(위 60 사용)' : 'START_PX ' + Math.max(0, Math.round(r.start * 2) - FIX));
        if (stop) console.log(r.cut === null ? '멈출 문단 못 찾음(전체 사용)' : 'CUT_PX ' + (Math.round(r.cut * 2) - FIX));
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
