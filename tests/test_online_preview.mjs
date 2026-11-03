import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { runInNewContext } from 'node:vm';
import {
  createPreviewStore, validateRegionalCutoffs, buildPreviewCutoffs, previewContestDate, previewOrganization, previewNavigationGroups, compareOnlineRanks, buildPreviewPower, buildPreviewRanks, buildPreviewSchoolRanks,
  sortPreviewTeams, validatePreview, previewPowerMetricIds, searchPreviewTeams, formatPreviewTime,
} from '../static/js/preview.mjs';

function team(id, ranks, extra = {}) {
  return { id, school: id, name: id, sourceIndex: 0, members: [],
    onlineRanks: ranks, ratings: { currentSeason: null, cpcfinder: 0 },
    medals: { gold: 0, silver: 0, bronze: 0 }, ...extra };
}

test('Nanjing Chinese roster publishes four-dimensional preview with provisional special characters', async () => {
  const read = async path => JSON.parse(await readFile(new URL(path, import.meta.url), 'utf8'));
  const p = validatePreview(await read('../static/data/previews/icpc-2026-nanjing.json'));
  const roster = await read('../static/data/rosters/icpc-2026-nanjing.json');
  assert.equal(p.teams.length, 372);
  assert.equal(p.teams.filter(t => !t.excluded).length, 332);
  assert.equal(p.matchingSummary.members, 1116);
  assert.equal(p.hostSchool, '南京航空航天大学');
  assert.equal(p.dateOnly, true);
  assert.equal(formatPreviewTime(p), '比赛日期：2026年11月8日');
  assert.equal(p.teamSource.url, 'https://mp.weixin.qq.com/s/p2RZ4n0ZUIHEfM4AgfgCAQ');
  assert.equal(p.snapshotDate, '2026-11-03');
  assert.equal(p.unlisted, undefined);
  assert.deepEqual(previewPowerMetricIds(p), ['xcpcrating', 'xcpcElo', 'currentSeason', 'onlineRanks']);
  assert.equal(p.teams[194].name, '7'); // Chinese image overrides registration CSV's 0007.
  const special = p.teams[358];
  assert.equal(special.school, '南京外国语学校');
  assert.equal(special.name, '这㊣犸 n 乂ix ⧖ ၎昊ôᴬ○1');
  assert.deepEqual(special.members.map(m => m.name), ['高近仁', '曹轩铭', '逢锦骏']);
  assert.equal(special.excluded, true);
  assert.equal(roster.source.transcriptionNotes[0].status, 'provisional');
  assert.equal(roster.source.transcriptionNotes[0].value, special.name);
  for (const [i, t] of p.teams.entries()) {
    assert.equal(t.school, roster.teams[i].school);
    assert.equal(t.name, roster.teams[i].name);
    assert.equal(t.excluded, roster.teams[i].excluded);
    assert.deepEqual(t.members.map(m => m.name), roster.teams[i].members);
    for (const h of [...t.currentSeasonHistory, ...t.previousSeasonHistory]) {
      assert.ok(!h.contestId.includes('ladies'));
      assert.ok(Date.parse(h.startAt) < Date.parse(p.sortAt));
    }
  }
  assert.ok(!JSON.stringify(p.medalSources).includes('ladies'));
  for (const source of p.metricSources) {
    assert.ok(Date.parse(p.sourceSnapshots[source.id]) < Date.parse(p.sortAt));
    assert.equal(p.teams.flatMap(t => t.members).filter(m => m.ratings[source.id] !== null).length,
      p.matchingSummary[source.id]);
  }
  const leshan = validatePreview(await read('../static/data/previews/ccpc-2026-leshan.json'));
  const { selectPreviewContest } = await import('../static/js/preview.mjs');
  assert.equal(selectPreviewContest([leshan, p], null, null, new Date('2026-11-03T00:00:00+08:00')), p);
  assert.equal(previewNavigationGroups([leshan, p]).regional[0], p);
});

test('Leshan verified roster publishes current ratings and a clickable full preview', async () => {
  const read = async path => JSON.parse(await readFile(new URL(path, import.meta.url), 'utf8'));
  const p = validatePreview(await read('../static/data/previews/ccpc-2026-leshan.json'));
  const roster = await read('../static/data/rosters/ccpc-2026-leshan.json');
  assert.equal(p.teams.length, 348);
  assert.equal(p.teams.filter(t => !t.excluded).length, 300);
  assert.equal(p.matchingSummary.members, 1039);
  assert.equal(roster.source.sha256, '87db137b70960b9749eee2f0abd966a0807d10d1692543eca96f6ea81a7dbb7a');
  assert.equal(p.snapshotDate, '2026-11-02');
  assert.equal(p.sourceSnapshots.xcpcrating, '2026-11-01T11:26:37.766839+00:00');
  assert.equal(p.sourcesFetchedAt, '2026-11-01T16:20:55.575465+00:00');
  assert.equal(p.hostSchool, '乐山师范学院');
  assert.ok(!p.hideContestTime);
  assert.equal(p.dateOnly, true);
  assert.equal(formatPreviewTime(p), '比赛日期：2026年11月8日');
  assert.equal(previewContestDate(p), '2026-11-08');
  assert.equal(formatPreviewTime({ ...p, sortAt: '2026-11-07T16:00:00Z' }), '比赛日期：2026年11月8日');
  assert.throws(() => validatePreview({ ...p, dateOnly: 'true' }), /dateOnly/);
  assert.equal(p.sortAt, '2026-11-08T00:00:00+08:00');
  assert.deepEqual(previewPowerMetricIds(p), ['xcpcrating', 'xcpcElo', 'currentSeason', 'onlineRanks']);
  assert.equal(p.sourceSnapshots.currentSeason, '2026-11-01T10:00:00+08:00');
  assert.ok(p.teams.some(t => t.currentSeasonHistory.some(h => h.contestId === 'icpc2026wuhan')));
  assert.deepEqual(p.medalSources.addedContestIds, []);
  assert.ok(p.medalSources.cpcfinderCoveredContestIds.includes('icpc2026wuhan'));
  assert.ok(p.teams.flatMap(t => t.members).every(m => Object.values(m.medalSupplement).every(v => v === 0)));
  assert.equal(p.teams.flatMap(t => t.members).find(m => m.name === '赵嘉源').ratings.currentSeason, 1448);
  for (const [i, t] of p.teams.entries()) {
    assert.equal(t.school, roster.teams[i].school);
    assert.equal(t.name, roster.teams[i].name);
    assert.equal(t.excluded, roster.teams[i].excluded);
    assert.deepEqual(t.members.map(m => m.name), roster.teams[i].members);
    assert.ok(t.members.every(m => m.name !== '无无'));
  }
  assert.deepEqual(p.teams.find(t => t.name === 'Feel the Russian Style').members.map(m => m.name),
    ['蔡居宏', 'Timur Gizatullin', 'DEMIDOV Ilia']);
  for (const source of p.metricSources) {
    assert.ok(Date.parse(p.sourceSnapshots[source.id]) < Date.parse(p.sortAt));
    assert.equal(p.teams.flatMap(t => t.members).filter(m => m.ratings[source.id] !== null).length,
      p.matchingSummary[source.id]);
  }
  assert.equal(previewNavigationGroups([p]).regional[0], p);
  const summaries = (await read('../static/data/regional-cutoffs/2026-2027.json')).contests;
  const rows = previewNavigationGroups([p], p.id, summaries).regional.filter(t => t.id === p.id);
  assert.deepEqual(rows, [p]);
  assert.equal(rows[0].summaryOnly, undefined);
  assert.equal(p.unlisted, undefined);
  assert.deepEqual(buildPreviewCutoffs(p), { cup: 11, gold: 71, silver: 213, bronze: 451 });
  assert.deepEqual(summaries.find(t => t.id === p.id).cutoffs, buildPreviewCutoffs(p));
  const { selectPreviewContest } = await import('../static/js/preview.mjs');
  assert.equal(selectPreviewContest([p], null, null, new Date('2026-11-02T00:00:00+08:00')), p);
});

test('Wuhan is public and its complete preview replaces the cutoff summary', async () => {
  const wuhan = validatePreview(JSON.parse(await readFile(new URL('../static/data/previews/icpc-2026-wuhan.json', import.meta.url), 'utf8')));
  const summaries = JSON.parse(await readFile(new URL('../static/data/regional-cutoffs/2026-2027.json', import.meta.url), 'utf8')).contests;
  assert.equal(wuhan.unlisted, undefined);
  assert.equal(wuhan.teams.length, 438);
  assert.equal(wuhan.teams.filter(t => !t.excluded).length, 369);
  assert.equal(wuhan.teams.find(t => t.school === '河南师范大学' && t.name === '彩云归').excluded, false);
  const summary = summaries.find(t => t.id === wuhan.id);
  assert.equal(summary.officialTeamCount, 369);
  assert.equal(summary.excludedTeamCount, 69);
  assert.equal(summary.matchedOfficialTeamCount, 358);
  assert.deepEqual(summary.cutoffs, buildPreviewCutoffs(wuhan));
  assert.equal(wuhan.teams.flatMap(t => t.currentSeasonHistory).filter(h => h.contestId === 'icpc2026chengdu').length, 42);
  for (const current of ['icpc-2026-chengdu', wuhan.id]) {
    const rows = previewNavigationGroups([wuhan], current, summaries).regional.filter(p => p.id === wuhan.id);
    assert.equal(rows.length, 1);
    assert.equal(rows[0].summaryOnly, undefined);
    assert.equal(rows[0], wuhan);
    assert.deepEqual(buildPreviewCutoffs(rows[0]), { cup: 13, gold: 113, silver: 279, bronze: 673 });
  }
  const { selectPreviewContest } = await import('../static/js/preview.mjs');
  assert.equal(selectPreviewContest([wuhan], null, null, new Date('2026-10-28T00:00:00Z')), wuhan);
});
const dimensions = ['currentSeason', 'onlineRanks'];

test('Chengdu publishes updated ratings and four-dimensional power independent of last season', async () => {
  const preview = validatePreview(JSON.parse(await readFile(new URL('../static/data/previews/icpc-2026-chengdu.json', import.meta.url), 'utf8')));
  assert.equal(preview.teams.length, 328);
  assert.equal(preview.teams.filter(t => !t.excluded).length, 319);
  assert.equal(preview.matchingSummary.members, 982);
  assert.equal(preview.sourceSnapshots.xcpcrating, '2026-10-18T15:23:21.585592+00:00');
  assert.equal(preview.sourceSnapshots.xcpcElo, '2026-10-18T15:27:06.373Z');
  assert.deepEqual(previewPowerMetricIds(preview), ['xcpcrating', 'xcpcElo', 'currentSeason', 'onlineRanks']);
  assert.deepEqual(buildPreviewCutoffs(preview), { cup: 4, gold: 76, silver: 268, bronze: 599 });
  const power = buildPreviewPower(preview.teams, undefined, preview.powerMetrics);
  const changed = structuredClone(preview.teams);
  changed.forEach((team, i) => { team.ratings.previousSeason = i * 100000; });
  assert.deepEqual(buildPreviewPower(changed, undefined, preview.powerMetrics), power);
  for (const team of preview.teams) {
    assert.equal(power.get(team.id).counts.length, 4);
    if (team.excluded) assert.equal(power.get(team.id).rank, null);
  }
  assert.ok(preview.metricSources.some(s => s.id === 'previousSeason'));
  for (const source of preview.metricSources) {
    assert.equal(preview.matchingSummary[source.id], preview.teams.flatMap(t => t.members)
      .filter(m => m.ratings[source.id] !== null).length);
  }
  const summaries = validateRegionalCutoffs(JSON.parse(await readFile(new URL('../static/data/regional-cutoffs/2026-2027.json', import.meta.url), 'utf8')), '2026-2027');
  const group = previewNavigationGroups([preview], preview.id, summaries.contests);
  assert.equal(group.regional.filter(p => p.id === preview.id).length, 1);
  assert.equal(group.regional.find(p => p.id === preview.id).summaryOnly, undefined);
});

test('preview columns show current season before previous season without mutating sources', async () => {
  const source = await readFile(new URL('../static/js/app.mjs', import.meta.url), 'utf8');
  const order = runInNewContext(
    `${source.match(/function previewColumnSources\([^]*?\n\}/)[0]}\npreviewColumnSources`,
  );
  for (const ids of [
    ['xcpcrating', 'xcpcElo', 'previousSeason', 'currentSeason', 'cpcfinder'],
    ['xcpcrating', 'previousSeason', 'cpcfinder'],
    ['currentSeason', 'previousSeason'],
    ['currentSeason'],
  ]) {
    const sources = ids.map(id => ({ id }));
    const actual = Array.from(order(sources), s => s.id);
    const expected = ids.includes('currentSeason') && ids.includes('previousSeason')
      ? ids.filter(id => id !== 'currentSeason').flatMap(id => id === 'previousSeason' ? ['currentSeason', id] : [id])
      : ids;
    assert.deepEqual(actual, expected);
    assert.deepEqual(sources.map(s => s.id), ids);
  }
  assert.match(source, /for \(const source of previewColumnSources\(state.preview.metricSources\)\) \{/);
  assert.match(source, /for \(const source of previewColumnSources\(state.preview.metricSources\)\) row.append/);
});

test('online ranks keep three fixed numeric slots and centered subtitle', async () => {
  const source = await readFile(new URL('../static/js/app.mjs', import.meta.url), 'utf8');
  const render = runInNewContext(
    `${source.match(/function previewOnlineRankNode\([^]*?\n\}/)[0]}\npreviewOnlineRankNode`,
    {
      state: { preview: { onlineContests: ['ICPC1', 'ICPC2', 'CCPC'].map(title => ({ title })) } },
      node: (tag, props, children = []) => ({ tag, ...props, children }),
    },
  );
  for (const ranks of [[3, 8, 19], [1048, 7, 928], [null, 48, null]]) {
    const rendered = render(ranks);
    assert.equal(rendered.children.length, 5);
    assert.deepEqual(Array.from(rendered.children.filter(c => c.className === 'preview-online-rank'), c => c.text), ranks.map(r => String(r ?? '—')));
    assert.equal(rendered.children.map(c => c.text).join(''), ranks.map(r => r ?? '—').join(' / '));
    assert.match(rendered['aria-label'], /ICPC1：.+；ICPC2：.+；CCPC：/);
  }
  const css = await readFile(new URL('../static/styles.css', import.meta.url), 'utf8');
  assert.match(css, /\.preview-online-values\s*\{[^}]*grid-template-columns:\s*4ch 1\.2ch 4ch 1\.2ch 4ch/);
  assert.match(css, /\.preview-online-order\s*\{[^}]*text-align:\s*center/);
});

test('online ranks compare best, second best and third best independent of display order', () => {
  assert.equal(compareOnlineRanks([30, 1, 20], [1, 20, 30]), 0);
  assert.equal(compareOnlineRanks([2, 3, 4], [1, 999, null]), -1);
  assert.equal(compareOnlineRanks([5, 10, 30], [10, 5, 40]), 1);
  assert.equal(compareOnlineRanks([null, 5, 10], [5, 10, 30]), -1);
  assert.equal(compareOnlineRanks([null, null, null], null), 0);
});

test('online column gives global competition ranks, skips excluded and keeps missing last both ways', () => {
  const teams = [team('a', [1, 20, 30]), team('b', [20, 1, 30]),
    team('c', [1, 20, 40]), team('d', [null, null, null]),
    team('star', [1, 2, 3], { excluded: true })];
  const ranks = buildPreviewRanks(teams);
  assert.deepEqual(teams.map(t => ranks.get(t.id).onlineRanks), [1, 1, 3, null, null]);
  assert.deepEqual(sortPreviewTeams(teams, 'onlineRanks').map(t => t.id), ['star', 'a', 'b', 'c', 'd']);
  assert.deepEqual(sortPreviewTeams(teams, 'onlineRanks', 'asc').map(t => t.id), ['c', 'a', 'b', 'star', 'd']);
  const schools = buildPreviewSchoolRanks(sortPreviewTeams(teams, 'onlineRanks'), 'onlineRanks');
  assert.equal(schools.get('a'), 1);
  assert.equal(schools.get('b'), 1);
  assert.equal(schools.get('c'), 3);
  assert.equal(schools.has('star'), false);
});

test('power uses online ranks and ignores CPC Finder and medals, including data availability', () => {
  const teams = [team('a', [10, 20, 30]), team('b', [20, 30, 40]),
    team('empty', [null, null, null]), team('star', [1, 2, 3], { excluded: true })];
  const initial = buildPreviewPower(teams, undefined, dimensions);
  assert.deepEqual(initial.get('a').counts, [0, 2]);
  assert.equal(initial.get('a').rank, 1);
  assert.equal(initial.get('b').rank, 2);
  assert.equal(initial.get('star').rank, null);
  teams[2].ratings.cpcfinder = 999999;
  teams[2].medals.gold = 9999;
  assert.deepEqual(buildPreviewPower(teams, undefined, dimensions), initial);
  assert.equal(initial.get('empty').rank, null);
  assert.equal(buildPreviewRanks(teams).get('empty').ratings.cpcfinder, 1);
  assert.equal(buildPreviewRanks(teams).get('empty').medals, 1);
  assert.deepEqual(searchPreviewTeams(teams, 'a').map(t => t.id), ['a', 'star']);
});

async function xian() {
  return JSON.parse(await readFile(new URL('../static/data/previews/icpc-2026-xian.json', import.meta.url), 'utf8'));
}

test('Changchun is a public regional preview with the complete roster and five power dimensions', async () => {
  const preview = validatePreview(JSON.parse(await readFile(new URL('../static/data/previews/ccpc-2026-changchun.json', import.meta.url), 'utf8')));
  assert.equal(preview.teams.length, 336);
  assert.equal(new Set(preview.teams.map(t => t.school)).size, 209);
  assert.equal(preview.teams.flatMap(t => t.members).length, 1007);
  assert.equal(preview.contestStage, 'regional');
  assert.ok(!preview.hideContestTime);
  assert.equal(preview.title, '2026年CCPC国赛（长春）');
  assert.equal(preview.sortAt, '2026-10-18T09:00:00+08:00');
  assert.equal(preview.endAt, '2026-10-18T14:00:00+08:00');
  assert.equal(formatPreviewTime(preview), '比赛时间：2026年10月18日 09:00–14:00');
  assert.ok(!preview.unlisted);
  assert.equal(preview.teams.filter(t => t.excluded).length, 36);
  assert.equal(preview.teams.filter(t => !t.excluded).length, 300);
  assert.equal(preview.teams.find(t => t.school === '长春工业大学' && t.name === '力拔山兮').excluded, false);
  assert.equal(preview.teams.find(t => t.school === '湖南农业大学' && t.name === '零罚时').excluded, false);
  assert.equal(preview.teams.find(t => t.school === '琼台师范学院' && t.name === '贪得吴彦组').excluded, true);
  assert.deepEqual(previewPowerMetricIds(preview), ['xcpcrating', 'xcpcElo', 'previousSeason', 'currentSeason', 'onlineRanks']);
  const power = buildPreviewPower(preview.teams, undefined, preview.powerMetrics);
  assert.equal(power.size, 336);
  const ranks = buildPreviewRanks(preview.teams, preview.metricSources.map(s => s.id));
  for (const team of preview.teams.filter(t => t.excluded)) {
    assert.equal(power.get(team.id).rank, null);
    assert.equal(ranks.get(team.id).onlineRanks, null);
  }
  const index = JSON.parse(await readFile(new URL('../static/data/index.json', import.meta.url), 'utf8'));
  assert.ok(index.series.find(s => s.id === preview.seriesId).previews.some(p => p.id === preview.id));
});

test('contest time visibility validates booleans and resets on contest switches', async () => {
  const original = await xian();
  assert.equal(formatPreviewTime(original), '比赛时间：2026年10月18日 09:00');
  assert.equal(formatPreviewTime({ ...original, hideContestTime: true }), '');
  assert.equal(formatPreviewTime({ ...original, endAt: '2026-10-19T06:00:00Z' }), '比赛时间：2026年10月18日 09:00–2026年10月19日 14:00');
  for (const endAt of [null, 'bad', original.sortAt, '2026-10-17T14:00:00+08:00']) {
    assert.throws(() => validatePreview({ ...original, endAt }));
  }
  for (const value of [null, 'true', 0]) {
    const preview = await xian();
    preview.hideContestTime = value;
    assert.throws(() => validatePreview(preview));
  }
  const source = await readFile(new URL('../static/js/app.mjs', import.meta.url), 'utf8');
  const assignment = source.match(/document.querySelector\("#preview-time"\).hidden = [^;]+;/)[0];
  const time = { hidden: false };
  for (const hideContestTime of [true, undefined, false]) {
    runInNewContext(assignment, { document: { querySelector: () => time }, state: { preview: { hideContestTime } } });
    assert.equal(time.hidden, hideContestTime === true);
  }
});

test('Xian publication contains only roster identities and independently calculated five-dimensional power', async () => {
  const preview = validatePreview(await xian());
  assert.equal(preview.teams.length, 418);
  const official = preview.teams.filter(t => !t.excluded);
  assert.equal(official.length, 403);
  assert.equal(new Set(official.map(t => t.school)).size, 227);
  assert.equal(preview.teams.flatMap(t => t.members).length, 1253);
  assert.equal(official.flatMap(t => t.members).length, 1208);
  assert.deepEqual(preview.onlineContests.map(c => c.title), ['ICPC1', 'ICPC2', 'CCPC']);
  assert.deepEqual(previewPowerMetricIds(preview), ['xcpcrating', 'xcpcElo', 'previousSeason', 'currentSeason', 'onlineRanks']);
  const power = buildPreviewPower(preview.teams, undefined, preview.powerMetrics);
  assert.ok([...power.values()].every(p => p.counts.length === 5));
  const first = preview.teams.find(t => t.name === '遥不可及' && t.school === '清华大学');
  assert.deepEqual(first.onlineRanks, [2, 28, 20]);
  for (const source of preview.metricSources) assert.ok(Date.parse(preview.sourceSnapshots[source.id]) < Date.parse(preview.sortAt));
});

test('online schema rejects malformed ranks, wrong aggregation and invalid power dimensions', async () => {
  for (const mutate of [
    p => { p.teams[0].onlineRanks[0] = 0; },
    p => { p.teams[0].onlineRanks[0] = 99999; },
    p => { p.teams[0].members[0].onlineRanks = [1, 2]; },
    p => { p.onlineContests.reverse(); },
    p => { p.powerMetrics = ['unknown']; },
    p => { p.powerMetrics = ['onlineRanks', 'onlineRanks']; },
  ]) {
    const preview = await xian(); mutate(preview);
    assert.throws(() => validatePreview(preview));
  }
});


test('preview medal colors use independently rounded quotas and global competition ranks', async () => {
  const source = await readFile(new URL('../static/js/app.mjs', import.meta.url), 'utf8');
  const classify = runInNewContext(
    source.match(/function previewRankMedalClass\([^]*?\n\}/)[0] + '\npreviewRankMedalClass',
  );
  const color = (metric, rank, count, excluded = false) => classify(metric, rank, count, excluded, 'regional', ['onlineRanks', 'xcpcrating', 'xcpcElo', 'currentSeason', 'previousSeason']);
  for (const metric of ['power', 'onlineRanks', 'xcpcrating', 'xcpcElo', 'currentSeason', 'previousSeason']) {
    for (const [rank, expected] of [[1, 'gold'], [41, 'gold'], [42, 'silver'], [122, 'silver'], [123, 'bronze'], [243, 'bronze'], [244, null], [403, null]]) {
      assert.equal(color(metric, rank, 403), expected ? ' preview-medal-' + expected : '');
    }
    assert.deepEqual([40, 41, 41, 43].map(rank => color(metric, rank, 403)),
      [' preview-medal-gold', ' preview-medal-gold', ' preview-medal-gold', ' preview-medal-silver']);
    for (const rank of [null, undefined, 0, -1, 1.5, 404]) assert.equal(color(metric, rank, 403), '');
    assert.equal(color(metric, 1, 403, true), '');
  }
  for (const metric of ['cpcfinder', 'medals']) assert.equal(color(metric, 1, 403), '');
  assert.equal(color('power', 1, 0), '');
  assert.equal(color('power', 1, 1), ' preview-medal-gold');
  assert.equal(color('power', 2, 11), ' preview-medal-gold');
  assert.equal(color('power', 5, 11), ' preview-medal-silver');
  assert.equal(color('power', 9, 11), ' preview-medal-bronze');
  assert.equal(color('power', 10, 11), '');
  assert.match(source, /state\.preview\.teams\.filter\(team => !team\.excluded\)\.length/);
  assert.match(source, /previewRankMedalClass\("power", state\.previewPower\.get\(team\.id\)\.rank/);
  assert.match(source, /previewRankMedalClass\("onlineRanks", state\.previewRanks\.get\(team\.id\)\.onlineRanks/);
  assert.match(source, /previewRankMedalClass\(source\.id, rank, teamCount, team\.excluded, state\.preview\.contestStage, previewPowerMetricIds\(state\.preview\)\)/);
  for (const stage of [undefined, 'preliminary']) {
    for (const metric of ['power', 'onlineRanks', 'xcpcrating', 'xcpcElo', 'currentSeason', 'previousSeason']) {
      for (const rank of [1, 42, 123]) assert.equal(classify(metric, rank, 403, false, stage), '');
    }
  }
  const chengdu = JSON.parse(await readFile(new URL('../static/data/previews/icpc-2026-chengdu.json', import.meta.url), 'utf8'));
  assert.equal(classify('previousSeason', 1, 319, false, 'regional', previewPowerMetricIds(chengdu)), '');
  for (const metric of previewPowerMetricIds(chengdu)) assert.equal(classify(metric, 1, 319, false, 'regional', previewPowerMetricIds(chengdu)), ' preview-medal-gold');
  const xianPreview = validatePreview(await xian());
  assert.equal(xianPreview.contestStage, 'regional');
  assert.equal(classify('power', 1, 403, false, xianPreview.contestStage), ' preview-medal-gold');
  for (const file of ['2026-2027', 'icpc-2026-preliminary-2', 'ccpc-2026-preliminary']) {
    const preview = validatePreview(JSON.parse(await readFile(new URL('../static/data/previews/' + file + '.json', import.meta.url), 'utf8')));
    assert.equal(classify('power', 1, preview.teams.length, false, preview.contestStage), '');
  }
  for (const stage of [null, 'final', true]) {
    const invalid = await xian(); invalid.contestStage = stage;
    assert.throws(() => validatePreview(invalid), /contestStage/);
  }
});


test('unlisted previews stay out of navigation and default but remain accessible by explicit URL', async () => {
  const source = await readFile(new URL('../static/js/app.mjs', import.meta.url), 'utf8');
  const functions = ['selectLatestContest'].map(name =>
    source.match(new RegExp('function ' + name + '\\([^]*?\\n\\}'))[0]).join('\n');
  const { selectLatestContest } = runInNewContext(functions + '\n({ selectLatestContest })');
  const hidden = validatePreview({ ...await xian(), unlisted: true });
  const publicPreview = { id: 'ccpc-2026-preliminary', sortAt: '2026-09-19T13:00:00+08:00' };
  const previews = [hidden, publicPreview];
  assert.deepEqual(previewNavigationGroups(previews, publicPreview.id).regional, []);
  assert.deepEqual(previewNavigationGroups(previews, hidden.id).regional, [hidden]);
  assert.deepEqual(previewNavigationGroups(previews, hidden.id).online, [publicPreview]);
  assert.equal(selectLatestContest(previews, undefined, 'sortAt'), publicPreview);
  assert.equal(selectLatestContest(previews, 'unknown', 'sortAt'), publicPreview);
  assert.equal(selectLatestContest(previews, hidden.id, 'sortAt'), hidden);
  assert.equal(selectLatestContest([hidden], undefined, 'sortAt'), null);
  assert.equal(selectLatestContest([hidden], hidden.id, 'sortAt'), hidden);
  for (const value of [null, 1, 'true']) {
    const invalid = await xian(); invalid.unlisted = value;
    assert.throws(() => validatePreview(invalid), /unlisted/);
  }
});


test('cutoffs use school third, official quotas, best of three, and missing results', () => {
  const teams = Array.from({ length: 11 }, (_, i) => team(String(i), [100 + i, i + 1, null],
    { school: i < 2 ? 'same school' : String(i) }));
  const preview = { teams: [team('star', [1, 1, 1], { excluded: true }), ...teams] };
  const original = structuredClone(preview);
  assert.deepEqual(buildPreviewCutoffs(preview), { cup: 4, gold: 2, silver: 5, bronze: 9 });
  assert.deepEqual(preview, original);
  assert.deepEqual(buildPreviewCutoffs({ teams: [] }), { cup: null, gold: null, silver: null, bronze: null });
  teams.forEach(t => { t.onlineRanks = [null, null, null]; });
  teams[0].onlineRanks = [null, 7, null];
  assert.deepEqual(buildPreviewCutoffs(preview), { cup: null, gold: null, silver: null, bronze: null });
  assert.deepEqual(buildPreviewCutoffs({ teams: [teams[0]] }), { cup: null, gold: 7, silver: null, bronze: null });
});

test('cutoff ties retain the best rank and school deduplication', () => {
  const teams = [team('a', [10, 5, null]), team('b', [5, 9, null]),
    team('c', [5, 9, null]), team('d', [8, null, null])];
  assert.deepEqual(buildPreviewCutoffs({ teams }), { cup: 5, gold: 5, silver: 5, bronze: 8 });
});

test('published regional cutoff snapshots', async () => {
  assert.deepEqual(buildPreviewCutoffs(await xian()), { cup: 11, gold: 117, silver: 288, bronze: 658 });
  const changchun = JSON.parse(await readFile(new URL('../static/data/previews/ccpc-2026-changchun.json', import.meta.url), 'utf8'));
  assert.deepEqual(buildPreviewCutoffs(changchun), { cup: 10, gold: 84, silver: 252, bronze: 576 });
});

test('regional navigation orders Beijing calendar dates then ICPC before CCPC without mutating inputs', async () => {
  const regional = (id, sortAt, extra = {}) => ({ id, sortAt, contestStage: 'regional', ...extra });
  const previews = [
    regional('ccpc-late', '2026-10-19T01:00:00Z'),
    regional('ccpc-same', '2026-10-18T00:00:00Z'),
    regional('icpc-same', '2026-10-18T10:00:00Z'),
    regional('ccpc-earlier', '2026-10-16T16:00:00Z'),
    regional('icpc-midnight', '2026-10-17T16:30:00Z'),
    regional('icpc-unknown', '2026-10-01T00:00:00Z', { hideContestTime: true }),
  ];
  const original = structuredClone(previews);
  assert.deepEqual(previewNavigationGroups(previews).regional.map(p => p.id),
    ['ccpc-earlier', 'icpc-midnight', 'icpc-same', 'ccpc-same', 'ccpc-late', 'icpc-unknown']);
  assert.deepEqual(previews, original);
  assert.equal(previewContestDate(previews[4]), '2026-10-18');
  assert.equal(previewContestDate(previews[5]), null);
  assert.equal(previewOrganization(previews[0]), 'CCPC');
  assert.equal(previewOrganization({ id: 'other', title: 'Other event' }), null);
  const xianPreview = validatePreview(await xian());
  assert.equal(xianPreview.unlisted, undefined);
  assert.equal(xianPreview.hostSchool, '西北工业大学');
  const changchun = JSON.parse(await readFile(new URL('../static/data/previews/ccpc-2026-changchun.json', import.meta.url), 'utf8'));
  assert.deepEqual(previewNavigationGroups([changchun, xianPreview], changchun.id).regional.map(p => p.id),
    [xianPreview.id, changchun.id]);
  assert.equal(changchun.hostSchool, '东北师范大学');
  for (const hostSchool of [null, '', '  ', 123]) {
    assert.throws(() => validatePreview({ ...xianPreview, hostSchool }), /hostSchool/);
  }
});

test('summary-only stations validate, load independently, and yield to full previews', async () => {
  const document = JSON.parse(await readFile(new URL('../static/data/regional-cutoffs/2026-2027.json', import.meta.url), 'utf8'));
  validateRegionalCutoffs(document, '2026-2027');
  const [chengdu, wuhan, leshan] = document.contests;
  assert.deepEqual(chengdu.cutoffs, { cup: 4, gold: 76, silver: 268, bronze: 599 });
  assert.deepEqual([chengdu.teamCount, chengdu.officialTeamCount, chengdu.excludedTeamCount, chengdu.matchedOfficialTeamCount], [328, 319, 9, 310]);
  assert.equal(chengdu.sources.rosterFile, '成都最终强度表_20261012.xlsx');
  assert.equal(chengdu.sources.rosterSha256, '565da30b119eb38d3c07ada1909cfed9817c0622645c695a35e51a679a680b90');
  assert.deepEqual(wuhan.cutoffs, { cup: 13, gold: 113, silver: 279, bronze: 673 });
  const groups = previewNavigationGroups([await xian()], 'icpc-2026-xian', document.contests);
  assert.deepEqual(groups.regional.map(p => p.id), ['icpc-2026-xian', chengdu.id, wuhan.id, leshan.id]);
  assert.equal(groups.regional[1].summaryOnly, true);
  assert.equal(leshan.id, 'ccpc-2026-leshan');
  assert.equal(previewContestDate(leshan), '2026-11-08');
  assert.equal(leshan.hostSchool, '乐山师范学院');
  assert.deepEqual(leshan.cutoffs, { cup: 11, gold: 71, silver: 213, bronze: 451 });
  assert.deepEqual([leshan.teamCount, leshan.officialTeamCount, leshan.excludedTeamCount, leshan.matchedOfficialTeamCount], [348, 300, 48, 293]);
  assert.equal(groups.regional.at(-1).summaryOnly, true);
  assert.ok(!('teams' in leshan));
  assert.equal(previewNavigationGroups([{ ...chengdu, teams: [] }], chengdu.id, document.contests).regional[0].summaryOnly, undefined);
  const store = createPreviewStore('https://example.test/data/index.json', async url => {
    assert.equal(url, 'https://example.test/data/regional-cutoffs/2026-2027.json');
    return { ok: true, json: async () => document };
  });
  assert.deepEqual(await store.getRegionalCutoffs({ id: 'older' }), []);
  assert.deepEqual(await store.getRegionalCutoffs({ id: '2026-2027', regionalCutoffsPath: 'regional-cutoffs/2026-2027.json' }), document.contests);
  for (const edit of [d => { d.seriesId = 'other'; }, d => { d.contests.push(d.contests[0]); },
    d => { d.contests[0].cutoffs.gold = 0; }, d => { d.contests[0].sortAt = 'invalid'; },
    d => { d.contests[0].officialTeamCount = 999; }]) {
    const invalid = structuredClone(document); edit(invalid);
    assert.throws(() => validateRegionalCutoffs(invalid, '2026-2027'), /regionalCutoffs/);
  }
});
