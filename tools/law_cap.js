// 법령 조문 캡처 v2 (2026-11-25 주간 최적화에서 재작성)
// 옛 방식은 좌표(CUT_PX·START_PX, 보정 40px)로 잘라 11-21~23 세 글에서 제목·3호 줄이 잘렸습니다.
// 새 방식은 좌표를 쓰지 않습니다: div.pgroup 안 .lawcon의 자식 블록 중
// 시작 항 앞·멈출 항부터를 숨기고, 아이콘 줄(ul)·체크박스(input, span.checkbox)를 숨긴 뒤 .lawcon만 찍습니다.
//
// 실행(사용법은 옛것과 같음):
//   node tools/law_cap.js "법령명" "제8조(" 출력.png ["멈출항"] ["시작항"]
//   예) node tools/law_cap.js "도시 및 주거환경정비법" "제39조(" a.png "③"      → 제목~②항
//       node tools/law_cap.js "도시 및 주거환경정비법" "제39조(" a.png "③" "②" → ②항만(조 제목 줄은 남김)
//   다음 단계: python3 -I tools/cap.py 출력.png 최종.jpg   (좌표 없음)
//   조문을 못 찾거나 사이트 CSS가 안 먹은 화면(글꼴에 Pretendard 없음)이면
//   3000/6000/9000ms 기다리며 최대 3회 다시 열고, 마지막 시도는 그대로 받아들입니다.
const { chromium } = require('playwright');

const HIDE_CSS =
  '.law-hide{display:none!important}' +
  '.law-cap{width:600px!important;max-width:600px!important;overflow:visible!important;background:#fff;padding:14px 6px 14px 30px!important;box-sizing:content-box}' +
  '.law-cap *{white-space:normal!important;max-width:600px!important;word-break:keep-all}' +
  '.law-cap ul, .law-cap input, .law-cap span.checkbox{display:none!important}';

async function tryOnce(b, lawNm, jo, out, stop, start, wait, last) {
  const p = await b.newPage({ viewport: { width: 700, height: 4000 }, deviceScaleFactor: 2 });
  try {
    await p.goto('https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=0&lsNm=' + encodeURIComponent(lawNm),
      { waitUntil: 'networkidle', timeout: 90000 });
    await p.waitForTimeout(wait);
    for (const f of p.frames()) {
      for (const h of await f.$$('div.pgroup')) {
        const t = (await h.innerText()).trim();
        if (!t.startsWith(jo)) continue;
        const con = (await h.$('.lawcon')) || h;
        const font = await con.evaluate(n => getComputedStyle(n).fontFamily || '');
        if (!/pretendard/i.test(font) && !last) return { retry: 'CSS 미적용(글꼴: ' + font.slice(0, 40) + ')' };
        await f.addStyleTag({ content: HIDE_CSS });
        const info = await con.evaluate((n, [s, st]) => {
          n.classList.add('law-cap');
          const kids = Array.from(n.children);
          const idx = (pre) => pre ? kids.findIndex(c => (c.innerText || '').trim().startsWith(pre)) : -1;
          const si = idx(st), ei = idx(s);
          kids.forEach((c, i) => {
            if (si > 0 && i < si) c.classList.add('law-hide');   // 시작 항 앞(① 포함)을 숨김
            if (ei >= 0 && i >= ei) c.classList.add('law-hide');  // 멈출 항부터 숨김
          });
          if (si > 0) {   // ①이 조 제목과 같은 줄에 있으므로 제목만 떼어 맨 위에 다시 씁니다.
            const m = (kids[0].innerText || '').trim().match(/^제\d+조(의\d+)?\([^)]*\)/);
            if (m) {
              const t = document.createElement('p');
              t.textContent = m[0];
              t.style.cssText = 'font-weight:700;margin:0 0 6px 0';
              n.insertBefore(t, kids[si]);
            }
          }
          // 화면에 떠 있는 버튼·머리줄(fixed·sticky)이 조문을 가리므로 모두 숨깁니다.
          for (const e of n.ownerDocument.querySelectorAll('body *')) {
            const pos = getComputedStyle(e).position;
            if ((pos === 'fixed' || pos === 'sticky') && !e.contains(n)) e.classList.add('law-hide');
          }
          n.ownerDocument.defaultView.scrollTo(0, 0);
          return { n: kids.length, si, ei };
        }, [stop || '', start || '']);
        await p.waitForTimeout(500);
        await con.screenshot({ path: out });
        console.log(t.slice(0, 300));
        console.log('블록 %d개, 시작 %s, 멈춤 %s, 글꼴 %s', info.n,
          start ? (info.si < 0 ? '못 찾음(처음부터)' : info.si) : '-',
          stop ? (info.ei < 0 ? '못 찾음(끝까지)' : info.ei) : '-', font.slice(0, 30));
        return { ok: true };
      }
    }
    return { retry: '조문 못 찾음' };
  } finally {
    await p.close();
  }
}

(async () => {
  const [lawNm, jo, out, stop, start] = process.argv.slice(2);
  if (!lawNm || !jo || !out) {
    console.error('사용법: node tools/law_cap.js "법령명" "제8조(" 출력.png ["멈출항"] ["시작항"]');
    process.exit(1);
  }
  const b = await chromium.launch();
  try {
    const waits = [3000, 6000, 9000];
    for (let i = 0; i < waits.length; i++) {
      const r = await tryOnce(b, lawNm, jo, out, stop, start, waits[i], i === waits.length - 1);
      if (r.ok) return;
      console.error('다시 시도 %d/3: %s', i + 1, r.retry);
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
