// 정비사업 정보몽땅 추진현황 표에서 키워드가 든 줄만 남겨 캡처 (2026-11-18 목동 재건축 순서 글)
// 1번 소제목(지금 어느 단계일까)의 단지별 단계·고시일 근거를 웹검색 0회로 확보합니다.
//
// 실행:
//   node tools/cleanup_table.js "목동" 출력.png [표 주소]
//   - 표 주소 기본값: 재건축 신속통합기획 선정구역 추진현황(publicIntgrPlanSttn2.do)
//   - 키워드가 든 줄이 가장 많은 표 하나만 남기고, 나머지 줄은 숨긴 뒤 표만 찍습니다.
//   - 출력된 줄 내용(구역명·세대수·단계·고시일)을 원고 숫자와 대조합니다.
//   - 다음 단계: python3 -I tools/cap.py 출력.png 최종.jpg 0 0 1 1 24
//   - 한 단지가 다른 표(예: 목동6단지)에 있으면 이 그림에 빠지므로 출력 목록으로 확인합니다.
const { chromium } = require('playwright');

(async () => {
  const [kw, out, url] = process.argv.slice(2);
  if (!kw || !out) {
    console.error('사용법: node tools/cleanup_table.js "키워드" 출력.png [표 주소]');
    process.exit(1);
  }
  const target = url || 'https://cleanup.seoul.go.kr/cleanup/view/publicIntgrPlanSttn2.do';
  const b = await chromium.launch();
  try {
    const p = await b.newPage({ viewport: { width: 1000, height: 3000 }, deviceScaleFactor: 2 });
    await p.goto(target, { waitUntil: 'networkidle', timeout: 90000 });
    await p.waitForTimeout(2000);
    const info = await p.evaluate((kw) => {
      const tables = [...document.querySelectorAll('table')];
      let best = null, bestN = 0;
      const r = [];
      for (const [i, t] of tables.entries()) {
        const rows = [...t.querySelectorAll('tbody tr')];
        const n = rows.filter(tr => tr.innerText.includes(kw)).length;
        r.push(`표${i}: 전체 ${rows.length}줄, '${kw}' ${n}줄`);
        if (n > bestN) { best = t; bestN = n; }
      }
      if (best) {
        best.querySelectorAll('tbody tr').forEach(tr => { if (!tr.innerText.includes(kw)) tr.style.display = 'none'; });
        best.id = 'cap-table';
      }
      return r.join('\n');
    }, kw);
    console.log(info);
    const el = await p.$('#cap-table');
    if (!el) { console.error(`'${kw}' 줄이 있는 표 없음`); process.exitCode = 2; return; }
    console.log((await el.innerText()).slice(0, 2000));
    await el.screenshot({ path: out });
  } catch (e) {
    console.error('오류', e.message);
    process.exitCode = 1;
  } finally {
    await b.close();
  }
})();
