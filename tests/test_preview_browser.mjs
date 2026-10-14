import assert from 'node:assert/strict';
import test from 'node:test';
import { mkdir, writeFile } from 'node:fs/promises';

const debuggerUrl = process.env.PREVIEW_BROWSER_URL;
const siteUrl = process.env.PREVIEW_SITE_URL || 'http://127.0.0.1:8000/';

test('preview navigation: desktop/mobile, dates, hosts, public rows, switching and history', {
  skip: !debuggerUrl, timeout: 60000,
}, async () => {
  const target = await (await fetch(`${debuggerUrl}/json/new?about:blank`, { method: 'PUT' })).json();
  const socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise(resolve => socket.addEventListener('open', resolve, { once: true }));
  let id = 0;
  const pending = new Map(), errors = [];
  socket.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails);
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
    const result = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    assert.equal(result.exceptionDetails, undefined);
    return result.result.value;
  };
  const waitFor = async expression => {
    for (let i = 0; i < 150; i++) {
      if (await evaluate(expression)) return;
      await new Promise(resolve => setTimeout(resolve, 50));
    }
    assert.fail(`Timed out: ${expression}`);
  };
  const current = id => `document.querySelector('#preview-navigation button[aria-pressed="true"]')?.dataset.previewId === '${id}'`;
  try {
    await send('Page.enable');
    await send('Page.addScriptToEvaluateOnNewDocument', { source: `{
      const OriginalDate = Date;
      const now = OriginalDate.parse('2026-10-14T12:00:00+08:00');
      window.Date = class extends OriginalDate {
        constructor(...args) { super(...(args.length ? args : [now])); }
        static now() { return now; }
      };
    }` });
    await send('Runtime.enable');
    for (const width of [1440, 390]) {
      await send('Emulation.setDeviceMetricsOverride', { width, height: 1000, deviceScaleFactor: 1, mobile: width === 390 });
      await send('Page.navigate', { url: `${siteUrl}?series=2026-2027&view=preview` });
      await waitFor(`document.querySelector('#preview-navigation button[aria-pressed="true"]') !== null`);
      await evaluate(`localStorage.removeItem('xcpc-sight:preview-contest:2026-2027')`);
      await send('Page.navigate', { url: `${siteUrl}?series=2026-2027&view=preview` });
      await waitFor(current('icpc-2026-xian'));
      assert.equal(await evaluate(`localStorage.getItem('xcpc-sight:preview-contest:2026-2027')`), null);
      await evaluate(`document.querySelector('tr[data-preview-id="ccpc-2026-changchun"] td').click()`);
      await waitFor(current('ccpc-2026-changchun'));
      assert.equal(await evaluate(`localStorage.getItem('xcpc-sight:preview-contest:2026-2027')`), 'ccpc-2026-changchun');
      // Reopen the bare preview URL: restore the manual choice across page loads.
      await send('Page.navigate', { url: `${siteUrl}?series=2026-2027&view=preview` });
      await waitFor(current('ccpc-2026-changchun'));
      assert.equal(await evaluate(`document.querySelector('#preview-team-source a').getAttribute('href')`), './sources/ccpc-2026-changchun/');
      const firstPower = await evaluate(`document.querySelector('#preview-body .preview-power-cell')?.textContent`);
      for (const [type, count] of [['official', 300], ['starred', 36], ['all', 336]]) {
        await evaluate(`document.querySelector('[data-team-type="${type}"]').click()`);
        await waitFor(`document.querySelector('#result-count').textContent === '${count} 支队伍'`);
        await waitFor(`document.querySelector('.preview-table').getAttribute('aria-rowcount') === '${count + 1}'`);
        assert.equal(await evaluate(`document.querySelector('#preview-team-filter [aria-pressed="true"]').dataset.teamType`), type);
        if (type === 'official') assert.equal(await evaluate(`document.querySelector('#preview-body .preview-power-cell')?.textContent`), firstPower);
      }
      await evaluate('history.back()');
      await waitFor(`document.querySelector('#result-count').textContent === '36 支队伍'`);
      await evaluate('history.forward()');
      await waitFor(`document.querySelector('#result-count').textContent === '336 支队伍'`);
      assert.equal(await evaluate(`document.querySelector('#preview-team-filter').getBoundingClientRect().right <= innerWidth`), true);
      // A long second name must remain text that the cell can clip partway through,
      // including when its achievements make it a focusable tooltip trigger.
      await evaluate(`document.querySelector('#preview-body .preview-members-cell').scrollIntoView({block: 'center', inline: 'center'})`);
      await new Promise(resolve => setTimeout(resolve, 150));
      for (const achievements of [false, true]) {
        const result = await evaluate(`(() => {
          const cell = document.querySelector('#preview-body .preview-members-cell');
          cell.innerHTML = '<span class="preview-member-name">名字</span> / '
            + (${achievements} ? '<span class="preview-member-control" tabindex="0">' : '')
            + '<span class="preview-member-name">较长的名字很长很长很长</span>'
            + (${achievements} ? '</span>' : '') + ' / <span class="preview-member-name">名字</span>';
          const name = cell.querySelectorAll('.preview-member-name')[1];
          const range = document.createRange();
          range.setStart(name.firstChild, 0); range.setEnd(name.firstChild, 3);
          return {nameDisplay: getComputedStyle(name).display,
            controlDisplay: cell.querySelector('.preview-member-control')
              ? getComputedStyle(cell.querySelector('.preview-member-control')).display : 'inline',
            prefixFits: range.getBoundingClientRect().right < cell.getBoundingClientRect().right - 15,
            overflows: cell.scrollWidth > cell.clientWidth};
        })()`);
        assert.deepEqual(result, {nameDisplay: 'inline', controlDisplay: 'inline', prefixFits: true, overflows: true});
      }
      if (process.env.PREVIEW_SCREENSHOT_DIR) {
        await mkdir(process.env.PREVIEW_SCREENSHOT_DIR, { recursive: true });
        const shot = await send('Page.captureScreenshot', { format: 'png' });
        await writeFile(`${process.env.PREVIEW_SCREENSHOT_DIR}/members-${width}.png`, Buffer.from(shot.data, 'base64'));
      }
      await evaluate('window.scrollTo(0, 0)');
      assert.deepEqual(await evaluate(`Array.from(document.querySelectorAll('tr[data-preview-id="ccpc-2026-changchun"] .preview-cutoff-value'), el => el.textContent)`), ['10', '84', '252', '576']);
      assert.equal(await evaluate(`document.querySelectorAll('#preview-online-navigation button').length`), 3);
      assert.deepEqual(await evaluate(`Array.from(document.querySelectorAll('.preview-cutoff-table tbody tr[data-preview-id]'), el => el.dataset.previewId)`),
        ['icpc-2026-xian', 'ccpc-2026-changchun']);
      assert.deepEqual(await evaluate(`Array.from(document.querySelectorAll('.preview-cutoff-table tbody tr'), el => [el.cells[1].textContent, el.cells[2].textContent])`),
        [['2026-10-18', '西北工业大学'], ['2026-10-18', '东北师范大学'],
          ['2026-10-25', '电子科技大学'], ['2026-11-01', '武汉大学']]);
      assert.equal(await evaluate(`document.querySelectorAll('.preview-summary-only button, .preview-summary-only a, .preview-summary-only[data-preview-id]').length`), 0);
      const beforeSummaryClick = await evaluate('location.href');
      await evaluate(`document.querySelector('.preview-summary-only td').click()`);
      assert.equal(await evaluate('location.href'), beforeSummaryClick);
      assert.equal(await evaluate(current('ccpc-2026-changchun')), true);
      assert.deepEqual(await evaluate(`Array.from(document.querySelectorAll('.preview-summary-only'), row => Array.from(row.querySelectorAll('.preview-cutoff-value'), el => el.textContent))`),
        [['4', '76', '258', '574'], ['13', '113', '279', '673']]);
      assert.equal(await evaluate(`document.querySelector('[data-preview-id="icpc-2026-xian"]') !== null`), true);
      assert.equal(await evaluate(`(() => {
        const online = document.querySelector('#preview-online-navigation').getBoundingClientRect();
        const table = document.querySelector('.preview-cutoff-table').getBoundingClientRect();
        return online.bottom <= table.top && table.right <= innerWidth && table.left >= 0;
      })()`), true);
      await evaluate(`document.querySelector('#preview-navigation').scrollIntoView({block: 'start'})`);
      if (process.env.PREVIEW_SCREENSHOT_DIR) {
        await mkdir(process.env.PREVIEW_SCREENSHOT_DIR, { recursive: true });
        const screenshot = await send('Page.captureScreenshot', { format: 'png' });
        await writeFile(`${process.env.PREVIEW_SCREENSHOT_DIR}/preview-${width}.png`, Buffer.from(screenshot.data, 'base64'));
      }
      await evaluate(`document.querySelector('[data-preview-id="icpc-2026-preliminary-1"]').click()`);
      await waitFor(current('icpc-2026-preliminary-1'));
      assert.equal(await evaluate(`new URL(location.href).searchParams.get('previewContest')`), 'icpc-2026-preliminary-1');
      await evaluate(`document.querySelector('tr[data-preview-id="ccpc-2026-changchun"] td').click()`);
      await waitFor(current('ccpc-2026-changchun'));
      await evaluate('history.back()');
      await waitFor(current('icpc-2026-preliminary-1'));
      await evaluate('history.forward()');
      await waitFor(current('ccpc-2026-changchun'));
      await send('Page.navigate', { url: `${siteUrl}?series=2026-2027&view=preview&previewContest=icpc-2026-xian` });
      await waitFor(current('icpc-2026-xian'));
      assert.equal(await evaluate(`document.querySelector('#preview-team-source a').getAttribute('href')`), './sources/icpc-2026-xian-manual.pdf');
      for (const [type, count] of [['official', 403], ['starred', 15], ['all', 418]]) {
        await evaluate(`document.querySelector('[data-team-type="${type}"]').click()`);
        await waitFor(`document.querySelector('#result-count').textContent === '${count} 支队伍'`);
      }
      assert.deepEqual(await evaluate(`Array.from(document.querySelectorAll('tr[data-preview-id="icpc-2026-xian"] .preview-cutoff-value'), el => el.textContent)`), ['11', '117', '288', '658']);
      await evaluate('window.previewReloadMarker = true');
      await send('Page.reload');
      await waitFor('window.previewReloadMarker === undefined');
      await waitFor(current('icpc-2026-xian'));
      await evaluate(`document.querySelector('button[data-preview-id="ccpc-2026-changchun"]').focus()`);
      assert.equal(await evaluate('document.activeElement.dataset.previewId'), 'ccpc-2026-changchun');
      await send('Page.bringToFront');
      await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, text: '\r' });
      await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 });
      await waitFor(current('ccpc-2026-changchun'));
      assert.equal(await evaluate(`document.querySelector('[data-preview-id="icpc-2026-xian"]') !== null`), true);
    }
    for (const width of [1440, 390]) {
      await send('Emulation.setDeviceMetricsOverride', { width, height: 1000, deviceScaleFactor: 1, mobile: width === 390 });
      await send('Page.navigate', { url: `${siteUrl}sources/ccpc-2026-changchun/` });
      await waitFor(`document.querySelectorAll('figure img').length === 10 && document.querySelector('img').naturalWidth > 0`);
      assert.equal(await evaluate(`document.documentElement.scrollWidth <= innerWidth`), true);
      assert.equal(await evaluate(`document.querySelectorAll('a[href$=".xlsx"]').length`), 0);
      assert.equal(await evaluate(`Array.from(document.querySelectorAll('figure img')).every(img => img.parentElement.tagName === 'A' && img.parentElement.href === img.src)`), true);
      assert.equal(await evaluate(`document.querySelectorAll('figcaption a').length`), 0);
      if (process.env.PREVIEW_SCREENSHOT_DIR) {
        const shot = await send('Page.captureScreenshot', { format: 'png' });
        await writeFile(`${process.env.PREVIEW_SCREENSHOT_DIR}/sources-${width}.png`, Buffer.from(shot.data, 'base64'));
      }
      const originalImage = await evaluate(`document.querySelector('figure img').src`);
      await evaluate(`document.querySelector('figure img').click()`);
      await waitFor(`location.href === ${JSON.stringify(originalImage)}`);
    }
    assert.deepEqual(errors, []);
  } finally {
    socket.close();
    await fetch(`${debuggerUrl}/json/close/${target.id}`);
  }
});
