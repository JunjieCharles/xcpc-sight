// Optional local Chrome regression: see doc/post-contest-review.md for invocation.
import assert from "node:assert/strict";
import test from "node:test";

const debuggerUrl = process.env.REVIEW_BROWSER_URL;
const siteUrl = process.env.REVIEW_SITE_URL || "http://127.0.0.1:8000/";

test("changing review metrics preserves page and table scroll, clamping only at the end", {
  skip: !debuggerUrl, timeout: 30000,
}, async () => {
  const target = await (await fetch(`${debuggerUrl}/json/new?about:blank`, { method: "PUT" })).json();
  const socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise(resolve => socket.addEventListener("open", resolve, { once: true }));
  let id = 0;
  const pending = new Map();
  const errors = [];
  socket.addEventListener("message", event => {
    const message = JSON.parse(event.data);
    if (message.method === "Runtime.exceptionThrown") errors.push(message.params.exceptionDetails);
    const request = pending.get(message.id);
    if (!request) return;
    pending.delete(message.id);
    if (message.error) request.reject(new Error(JSON.stringify(message.error)));
    else request.resolve(message.result);
  });
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    pending.set(++id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params }));
  });
  const evaluate = async expression => {
    const result = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
    assert.equal(result.exceptionDetails, undefined);
    return result.result.value;
  };
  const waitFor = async expression => {
    for (let attempt = 0; attempt < 100; attempt++) {
      if (await evaluate(expression)) return;
      await new Promise(resolve => setTimeout(resolve, 50));
    }
    assert.fail(`Timed out waiting for ${expression}`);
  };
  const settle = () => evaluate("new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))");
  const position = () => evaluate("({ page: scrollY, table: document.querySelector('#review-scroll').scrollTop })");
  const checkMedalAlignment = async (container) => {
    const rows = await evaluate(`Array.from(document.querySelectorAll('${container} .preview-value-control > .medal-values, ${container} .preview-ranked-value > .medal-values'), el => ({
      icons: Array.from(el.querySelectorAll('.medal-icon'), n => n.getBoundingClientRect().left),
      counts: Array.from(el.querySelectorAll('.medal-count'), n => n.getBoundingClientRect().right),
      inside: el.getBoundingClientRect().left >= el.closest('td').getBoundingClientRect().left
        && el.getBoundingClientRect().right <= el.closest('td').getBoundingClientRect().right,
    }))`);
    assert.ok(rows.length > 1, "check multiple medal rows");
    for (const row of rows) {
      assert.ok(row.inside, "medals must fit their table cell");
      for (let medal = 0; medal < 3; medal++) {
        assert.ok(Math.abs(row.icons[medal] - rows[0].icons[medal]) < .5, "medal icons must align");
        assert.ok(Math.abs(row.counts[medal] - rows[0].counts[medal]) < .5, "medal counts must align");
      }
    }
  };
  try {
    await send("Runtime.enable");
    await send("Network.enable");
    await send("Network.setCacheDisabled", { cacheDisabled: true });
    for (const width of [1920, 390]) {
      await send("Emulation.setDeviceMetricsOverride", { width, height: 900, deviceScaleFactor: 1, mobile: width === 390 });
      await send("Page.navigate", { url: new URL("?series=2026-2027&view=review", siteUrl).href });
      await waitFor("document.querySelectorAll('.review-metric-card').length === 6 && !document.querySelector('#review-view').hidden");
      assert.equal(await evaluate("document.querySelector('.review-summary h3 small').textContent"), "Spearman ρ");
      assert.equal(await evaluate("document.querySelector('[data-metric=\"power\"] strong').textContent"), "0.736");
      await settle();
      assert.deepEqual(await evaluate(`Array.from(document.querySelectorAll('#review-head .review-original-rank'), el => el.textContent)`), ["（过滤前）", "（过滤前）"]);
      const rankPairs = await evaluate(`Array.from(document.querySelectorAll('#review-body tr:first-child .review-rank-pair'), el => ({
        text: el.textContent, label: el.getAttribute('aria-label'),
        color: getComputedStyle(el.querySelector('small')).color,
        muted: getComputedStyle(document.querySelector('.preview-sources')).color,
        fits: el.getBoundingClientRect().right <= el.closest('td').getBoundingClientRect().right,
      }))`);
      assert.equal(rankPairs.length, 2);
      assert.equal(rankPairs[0].text, "#23(#26)");
      for (const pair of rankPairs) {
        assert.match(pair.label, /过滤前第 \d+ 名/);
        assert.equal(pair.color, pair.muted);
        assert.ok(pair.fits);
      }
      for (const column of [5, 6]) {
        const edges = await evaluate(`Array.from(document.querySelectorAll('#review-body tr:not(.virtual-spacer) td:nth-child(${column}) .review-rank-pair'), el => ({
          filtered: el.children[0].getBoundingClientRect().right,
          original: el.children[1].getBoundingClientRect().right,
          fits: el.getBoundingClientRect().left >= el.closest('td').getBoundingClientRect().left,
        }))`);
        for (const edge of edges) {
          assert.ok(Math.abs(edge.filtered - edges[0].filtered) < .5, "filtered ranks must align");
          assert.ok(Math.abs(edge.original - edges[0].original) < .5, "original ranks must align");
          assert.ok(edge.fits);
        }
      }
      const changes = await evaluate(`Array.from(document.querySelectorAll('#review-body .review-rank-change'), el => ({
        arrow: el.querySelector('.review-change-arrow').getBoundingClientRect().left,
        number: el.querySelector('.review-change-number').getBoundingClientRect().left,
        value: el.querySelector('.review-change-number').textContent,
      }))`);
      assert.ok(new Set(changes.map(change => change.value.length)).size > 1, "check different digit counts");
      for (const change of changes) {
        assert.ok(Math.abs(change.arrow - changes[0].arrow) < .5, "arrows must align");
        assert.ok(Math.abs(change.number - changes[0].number) < .5, "number starts must align");
      }
      await evaluate(`(() => {
        const card = document.querySelector('[data-metric="cpcfinder"]');
        window.scrollTo(0, card.getBoundingClientRect().top + scrollY - 100);
        document.querySelector('#review-scroll').scrollTop = 2000;
      })()`);
      await settle();
      const before = await position();
      assert.ok(before.page > 0);
      await evaluate("document.querySelector('[data-metric=\"cpcfinder\"]').click()");
      await waitFor("document.querySelector('[data-metric=\"cpcfinder\"]').getAttribute('aria-pressed') === 'true'");
      await settle();
      assert.deepEqual(await position(), before, `metric switch moved the ${width}px viewport`);
      await evaluate("document.querySelector('[data-metric=\"power\"]').click()");
      await settle();
      await evaluate("document.querySelector('#review-scroll').scrollTop = 1e9");
      await settle();
      const pageBeforeClamp = (await position()).page;
      await evaluate("document.querySelector('[data-metric=\"cpcfinder\"]').click()");
      await settle();
      assert.equal((await position()).page, pageBeforeClamp);
      const last = await evaluate(`(() => {
        const shell = document.querySelector('#review-scroll');
        return { lastRow: Number(shell.querySelector('tbody tr:last-child').getAttribute('aria-rowindex')),
          rowCount: Number(shell.querySelector('table').getAttribute('aria-rowcount')) };
      })()`);
      assert.equal(last.lastRow, last.rowCount, "shrinking the cohort should still show its final row");
      await evaluate("document.querySelector('[data-metric=\"medals\"]').click()");
      await evaluate("document.querySelector('#review-scroll').scrollTop = 0");
      await settle();
      await checkMedalAlignment("#review-body");
      await evaluate("document.querySelector('#preview-tab').click()");
      await settle();
      await checkMedalAlignment("#preview-body");
    }
    assert.deepEqual(errors, []);
  } finally {
    await send("Page.close");
    socket.close();
  }
});
