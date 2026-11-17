// 경제 탭에서 '더보기'를 반복 클릭해(사람이 하는 것과 같은 동작) 나오는 블로그 메이트를 모두 모음
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 400, height: 900 } });
  const seen = {};
  p.on('response', async r => {
    if (!r.url().includes('m.blog.naver.com/api/v1/topic-contributors')) return;
    try {
      const j = JSON.parse(await r.text());
      for (const t of j.result || []) for (const c of t.contributors || []) {
        const id = c.profile.contributorHomeMobileUrl;
        const s = seen[id] || (seen[id] = { name: c.profile.displayName, url: id, aib: c.profile.cumulativeAibViewCount, titles: [] });
        const tt = c.representativeContent && c.representativeContent.contentTitle;
        if (tt && !s.titles.includes(tt)) s.titles.push(tt);
      }
    } catch (e) {}
  });
  await p.goto('https://mate.naver.com/?topicId=TOPIC_021&fieldId=insight#partners', { timeout: 60000, waitUntil: 'networkidle' }).catch(e => console.log('goto', e.message));
  await p.getByRole('button', { name: '경제' }).first().click().catch(() => {});
  let last = 0, still = 0;
  for (let i = 0; i < 150 && still < 25; i++) {
    await p.getByText('더보기', { exact: true }).first().click().catch(() => {});
    await p.waitForTimeout(1200);
    const n = Object.keys(seen).length;
    still = n === last ? still + 1 : 0; last = n;
  }
  fs.writeFileSync('data/mate_econ_raw.json', JSON.stringify(Object.values(seen), null, 1));
  console.log('unique blog mates:', Object.keys(seen).length);
  await b.close();
})();
