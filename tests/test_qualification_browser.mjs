// Optional HTTP/Chrome verification; screenshots stay under ignored outputs/.
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import test from "node:test";

const debuggerUrl = process.env.QUALIFICATION_BROWSER_URL;
const siteUrl = process.env.QUALIFICATION_SITE_URL || "http://127.0.0.1:8016/";

test("qualification tabs, deep links, filters and shared responsive layout", { skip: !debuggerUrl, timeout: 90000 }, async () => {
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
    for (let i = 0; i < 120; i++) {
      if (await evaluate(expression)) return;
      await new Promise(resolve => setTimeout(resolve, 60));
    }
    assert.fail(`Timed out: ${expression}`);
  };
  try {
    await send("Runtime.enable");
    await send("Page.enable");
    await mkdir("outputs/qualification", { recursive: true });
    const layout = () => evaluate(`(() => {
      const main = document.querySelector('main');
      const sidebar = document.querySelector('.series-sidebar').getBoundingClientRect();
      const content = document.querySelector('.app-content').getBoundingClientRect();
      return { mainWidth: main.getBoundingClientRect().width, sidebarX: sidebar.x, sidebarWidth: sidebar.width, contentX: content.x, contentWidth: content.width, columns: getComputedStyle(main).gridTemplateColumns };
    })()`);
    for (const [width, height] of [[2560, 1440], [1920, 1080], [1440, 1000], [1024, 768], [844, 390], [390, 844]]) {
      await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: width <= 844 });
      await send("Page.navigate", { url: `${siteUrl}?series=2026-2027` });
      await waitFor("document.querySelector('#participant-rating-tab').getAttribute('aria-selected') === 'true' && !document.querySelector('#series-view').hidden");
      const sharedLayout = await layout();
      assert.ok(sharedLayout.mainWidth >= width - 20, "all pages use the available viewport width");
      assert.ok(sharedLayout.sidebarX <= 32, "outer whitespace stays small");
      if (width > 850) assert.ok(sharedLayout.contentX >= sharedLayout.sidebarX + sharedLayout.sidebarWidth, "SERIES stays left on desktop");
      else assert.equal(sharedLayout.sidebarX, sharedLayout.contentX, "narrow screens share a stacked layout");
      const checkLayout = async name => {
        assert.deepEqual(await layout(), sharedLayout, `${name}: shared navigation and content geometry`);
        assert.equal(await evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), true, name);
        await evaluate("scrollTo(0, 0)");
        await new Promise(resolve => setTimeout(resolve, 80));
        const shot = await send("Page.captureScreenshot", { format: "png" });
        await writeFile(`outputs/qualification/layout-${name}-${width}.png`, Buffer.from(shot.data, "base64"));
      };
      await checkLayout("rating");
      let safeStyle;
      for (const mode of ["wf", "ecf"]) {
        await send("Page.navigate", { url: `${siteUrl}?series=2026-2027&view=${mode}` });
        await waitFor(`!document.querySelector('#qualification-view').hidden && document.querySelector('#${mode}-tab').getAttribute('aria-selected') === 'true'`);
        await checkLayout(mode);
        const currentSafeStyle = await evaluate("(() => { const style = getComputedStyle(document.querySelector('td.qualification-safe')); return { background: style.backgroundColor, color: style.color, emphasis: style.boxShadow }; })()");
        if (mode === "wf") safeStyle = currentSafeStyle;
        else assert.deepEqual(currentSafeStyle, safeStyle, "both boards share the same confirmed-place styling");
        assert.notEqual(currentSafeStyle.emphasis, "none");
        assert.equal(await evaluate("document.querySelector('.qualification-disclaimer').textContent"), "民间数据，仅供参考，不代表官方结果");
        assert.equal(await evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), true);
        assert.equal(await evaluate("document.querySelectorAll('.qualification-method, .qualification-station-nav, #qualification-view input[type=number]').length"), 0);
        assert.equal(await evaluate("document.querySelectorAll('.qualification-stats, .qualification-explanation, .qualification-assumption').length"), 0);
        assert.equal(await evaluate("document.querySelector('.qualification-disclaimer').nextElementSibling.className"), "qualification-legend");
        const pressureTitles = await evaluate("['low', 'medium', 'high'].map(level => document.querySelector('.qualification-legend .qualification-pressure-' + level).title)");
        assert.deepEqual(pressureTitles, [
          "低：前方未赛位置全部新增占位，仍有足够的总名额；具体资格还受同校竞争等因素影响。",
          "中：前方超过一半的未赛位置新增占位，才会触及总名额限制。",
          "高：前方一半或更少的未赛位置新增占位，就会触及总名额限制。",
        ]);
        assert.equal(await evaluate("document.querySelectorAll('.qualification-boundary, .qualification-risk').length"), 0);
        assert.equal(await evaluate("document.querySelectorAll('.qualification-host-mark').length"), mode === "wf" ? 1 : 0);
        if (mode === "wf") {
          assert.equal(await evaluate("document.querySelector('.qualification-host-mark').textContent"), "承办学校");
          assert.match(await evaluate("document.querySelector('.qualification-host-mark').title"), /沈阳站校排第 7.*资格待核验/);
          assert.equal(await evaluate("getComputedStyle(document.querySelector('td.qualification-host-performance')).backgroundColor"), "rgb(233, 220, 243)");
          assert.equal(await evaluate("(() => { const tag = document.querySelector('.qualification-host-mark'); const a = tag.getBoundingClientRect(); const b = tag.previousElementSibling.getBoundingClientRect(); const cell = tag.closest('td').getBoundingClientRect(); return a.left >= b.right && a.right <= cell.right && a.width > 0; })()"), true, "host marker fits beside school");
        }
        assert.equal(await evaluate("[...document.querySelectorAll('td[data-role=selected][data-certainty=risk] .qualification-badge')].every(b => b.textContent === '当前出线 待定')"), true);
        assert.ok(await evaluate("document.querySelectorAll('td.qualification-pressure-high').length > 0"));
        if (mode === "ecf") assert.ok(await evaluate("document.querySelectorAll('td.qualification-pressure-low').length > 0"));
        assert.equal(await evaluate("document.querySelectorAll('td.qualification-region-top').length"), mode === "wf" ? 8 : 7);
        assert.equal(await evaluate("document.querySelectorAll('td.qualification-region-bottom').length"), mode === "wf" ? 8 : 7);
        assert.equal(await evaluate("document.querySelectorAll('td.qualification-final.qualification-region-edge').length"), 0);
        assert.equal(await evaluate("[...document.querySelectorAll('td.qualification-region-bottom')].every(cell => getComputedStyle(cell).borderBottomWidth === '3px')"), true);
        assert.equal(await evaluate("(() => { const card = document.querySelector('.qualification-team').getBoundingClientRect(); const badge = document.querySelector('.qualification-badge').getBoundingClientRect(); const school = document.querySelector('.qualification-school').getBoundingClientRect(); return Math.abs(card.right - badge.right) < 1 && Math.abs(card.top - badge.top) < 1 && (school.top >= badge.bottom - 1 || school.right <= badge.left + 1); })()"), true, "tag is pinned top-right without overlapping school");
        if (width === 2560) assert.equal(await evaluate("Math.max(...[...document.querySelectorAll('.qualification-table tbody tr')].map(row => row.getBoundingClientRect().height)) < 70"), true, "wide closed cards stay compact");
        assert.equal(await evaluate("document.querySelectorAll('.qualification-search-navigation button:disabled').length"), 2);
        if (mode === "wf") assert.match(await evaluate("document.querySelector('.qualification-channels').textContent"), /总名额 16 个/);
        assert.equal(await evaluate("(() => { const widths = Array.from(document.querySelectorAll('.qualification-table thead th')).slice(1).map(cell => cell.getBoundingClientRect().width); return Math.max(...widths) - Math.min(...widths) < 1; })()"), true, "all station columns have equal width, including pending and EC Final");
        if (width >= 740) {
          assert.equal(await evaluate("document.querySelector('.qualification-scroll').scrollWidth <= document.querySelector('.qualification-scroll').clientWidth + 1"), true, `${mode} at ${width}: table fits`);
          assert.equal(await evaluate("document.querySelector('.qualification-table thead th:last-child').getBoundingClientRect().right <= document.querySelector('.qualification-scroll').getBoundingClientRect().right + 1"), true);
        }
        assert.ok(await evaluate("document.querySelectorAll('.qualification-safe').length > 1"));
        const rows = await evaluate("document.querySelectorAll('.qualification-table tbody tr').length");
        assert.ok(rows >= 5);
        await evaluate("document.querySelector('.qualification-team summary').click()");
        assert.equal(await evaluate("document.querySelector('.qualification-team').open"), true);
        assert.equal(await evaluate("getComputedStyle(document.querySelector('.qualification-team[open] .qualification-members')).whiteSpace"), "normal");
        await evaluate("document.querySelector('.qualification-team summary').click()");
        await evaluate("document.querySelector('#qualification-view').scrollIntoView({block: 'start'})");
        await new Promise(resolve => setTimeout(resolve, 150));
        const screenshot = await send("Page.captureScreenshot", { format: "png" });
        await writeFile(`outputs/qualification/${mode}-${width}.png`, Buffer.from(screenshot.data, "base64"));
        await evaluate("document.querySelector('.qualification-toolbar').scrollIntoView({block: 'start'})");
        await new Promise(resolve => setTimeout(resolve, 100));
        const tableScreenshot = await send("Page.captureScreenshot", { format: "png" });
        await writeFile(`outputs/qualification/${mode}-${width}-table.png`, Buffer.from(tableScreenshot.data, "base64"));
        if (mode === "ecf" && width === 2560) {
          await evaluate("const shell = document.querySelector('.qualification-scroll'); const end = [...document.querySelectorAll('td.qualification-region-bottom')].at(-1); shell.scrollTop = end.offsetTop - shell.clientHeight / 2;");
          const boundaryShot = await send("Page.captureScreenshot", { format: "png" });
          await writeFile("outputs/qualification/ecf-boundary.png", Buffer.from(boundaryShot.data, "base64"));
          await evaluate("document.querySelector('.qualification-scroll').scrollTop = 0");
        }
        await evaluate("document.querySelector('[aria-label=\"盘点搜索学校队伍成员\"]').value = '同济大学'; document.querySelector('[aria-label=\"盘点搜索学校队伍成员\"]').dispatchEvent(new Event('input'))");
        assert.ok(await evaluate("document.querySelectorAll('.qualification-match').length > 0"));
        const matchCount = await evaluate("document.querySelectorAll('.qualification-match').length");
        assert.ok(matchCount > 1);
        const activeIndex = () => evaluate("Array.from(document.querySelectorAll('.qualification-match')).findIndex(cell => cell.classList.contains('qualification-match-active'))");
        assert.equal(await activeIndex(), 0);
        const pageY = await evaluate("scrollY");
        await evaluate("document.querySelector('[aria-label=\"下一个搜索结果\"]').click()");
        assert.equal(await activeIndex(), 1);
        assert.match(await evaluate("document.querySelector('.qualification-toolbar [aria-live]').textContent"), /^2 \/ /);
        await evaluate("document.querySelector('[aria-label=\"上一个搜索结果\"]').click()");
        assert.equal(await activeIndex(), 0);
        await evaluate("document.querySelector('[aria-label=\"上一个搜索结果\"]').click()");
        assert.equal(await activeIndex(), matchCount - 1);
        assert.equal(await evaluate("scrollY"), pageY, "navigation only scrolls the table");
        assert.equal(await evaluate("(() => { const cell = document.querySelector('.qualification-match-active').getBoundingClientRect(); const shell = document.querySelector('.qualification-scroll').getBoundingClientRect(); const head = document.querySelector('.qualification-table thead').getBoundingClientRect(); return cell.top >= head.bottom - 1 && cell.top < shell.bottom; })()"), true, "active result is visible below sticky header");
        await evaluate("document.querySelector('[aria-label=\"盘点搜索学校队伍成员\"]').dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter'}))");
        assert.equal(await activeIndex(), 0);
        await evaluate("document.querySelector('[aria-label=\"盘点搜索学校队伍成员\"]').dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', shiftKey: true}))");
        assert.equal(await activeIndex(), matchCount - 1);
        await evaluate("document.querySelector('[aria-label=\"盘点搜索学校队伍成员\"]').value = '不存在的大学xyz'; document.querySelector('[aria-label=\"盘点搜索学校队伍成员\"]').dispatchEvent(new Event('input'))");
        assert.equal(await evaluate("document.querySelectorAll('.qualification-match').length"), 0);
        assert.match(await evaluate("document.querySelector('.qualification-toolbar [aria-live]').textContent"), /0 个匹配/);
        assert.equal(await evaluate("document.querySelectorAll('.qualification-search-navigation button:disabled').length"), 2);
        await evaluate("document.querySelector('[aria-label=\"盘点搜索学校队伍成员\"]').value = ''; document.querySelector('[aria-label=\"盘点搜索学校队伍成员\"]').dispatchEvent(new Event('input'))");
        assert.equal(await evaluate("document.querySelectorAll('.qualification-table tbody tr').length"), rows);
        assert.equal(await evaluate("document.querySelectorAll('.qualification-match-active').length"), 0);
        assert.equal(await evaluate("document.querySelectorAll('.qualification-search-navigation button:disabled').length"), 2);
      }
      await evaluate("document.querySelector('#wf-tab').click()");
      await waitFor("document.querySelector('#wf-tab').getAttribute('aria-selected') === 'true' && !document.querySelector('#qualification-view').hidden");
      assert.equal(await evaluate("new URL(location.href).searchParams.get('view')"), "wf");
      await evaluate("history.back()");
      await waitFor("document.querySelector('#ecf-tab').getAttribute('aria-selected') === 'true' && !document.querySelector('#qualification-view').hidden");
      await evaluate("document.querySelector('#review-tab').click()");
      await waitFor("!document.querySelector('#review-view').hidden");
      assert.equal(await evaluate("document.querySelector('#qualification-view').hidden"), true);
      await checkLayout("review");
      if (width >= 1920) {
        await waitFor("document.querySelector('#review-body tr:not(.virtual-spacer)') !== null");
        assert.equal(await evaluate("(() => { const shell = document.querySelector('#review-scroll'); return shell.scrollWidth <= shell.clientWidth + 1; })()"), true, "wide review has no horizontal scroll");
        assert.equal(await evaluate("(() => { const shell = document.querySelector('#review-scroll'); return Math.abs(shell.querySelector('table').getBoundingClientRect().width - shell.clientWidth) < 1; })()"), true, "review fills available width without clipping");
        await evaluate("document.querySelector('#review-scroll').scrollIntoView({block: 'start'})");
        const reviewShot = await send("Page.captureScreenshot", { format: "png" });
        await writeFile(`outputs/qualification/review-table-${width}.png`, Buffer.from(reviewShot.data, "base64"));
      }
      await evaluate("document.querySelector('#preview-tab').click()");
      await waitFor("!document.querySelector('#preview-view').hidden");
      await checkLayout("preview");
      await waitFor("document.querySelector('#preview-view .preview-table tbody tr:not(.virtual-spacer)') !== null");
      assert.equal(await evaluate("(() => { const table = document.querySelector('#preview-view .preview-table'); return table.getBoundingClientRect().width >= table.parentElement.clientWidth - 1; })()"), true, "preview table fills its container");
      if (width === 2560) {
        assert.equal(await evaluate("(() => { const table = document.querySelector('#preview-view .preview-table'); const cells = [...table.querySelectorAll('thead th')]; return Math.abs(table.getBoundingClientRect().width - table.parentElement.clientWidth) < 1 && [200, 170, 190].every((w, i) => Math.abs(cells[i].getBoundingClientRect().width - w) < 1); })()"), true, "wide preview fills container and retains frozen column widths");
      }
      await evaluate("document.querySelector('#preview-view .preview-table').parentElement.scrollIntoView({block: 'start'})");
      const previewTableShot = await send("Page.captureScreenshot", { format: "png" });
      await writeFile(`outputs/qualification/preview-table-${width}.png`, Buffer.from(previewTableShot.data, "base64"));
      await evaluate("document.querySelector('#participant-rating-tab').click()");
      await waitFor("!document.querySelector('#series-view').hidden");
      await evaluate("document.querySelector('[data-series-id=\"2025-2026\"]').click()");
      await waitFor("document.querySelector('[data-series-id=\"2025-2026\"]').getAttribute('aria-current') === 'page' && !document.querySelector('#series-view').hidden");
      assert.equal(await evaluate("document.querySelector('#wf-tab').hidden && document.querySelector('#ecf-tab').hidden"), true);
      await evaluate("document.querySelector('#problem-rating-tab').click()");
      await waitFor("!document.querySelector('#problem-rating-view').hidden");
      await checkLayout("problem-rating");
    }
    assert.deepEqual(errors, []);
  } finally {
    socket.close();
    await fetch(`${debuggerUrl}/json/close/${target.id}`);
  }
});
