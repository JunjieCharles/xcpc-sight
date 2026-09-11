import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { runInNewContext } from "node:vm";

import {
  buildPreviewPower,
  normalizedLseRating,
  buildPreviewRanks,
  buildPreviewSchoolRanks,
  bestAchievementMedal,
  achievementDisplayParts,
  createPreviewStore,
  previewRatingValue,
  readPreviewQuery,
  searchPreviewTeams,
  sortPreviewTeams,
  validatePreview,
  writePreviewQuery,
} from "../static/js/preview.mjs";

test("loads both published previews from the index and preserves contest selection", async () => {
  const root = new URL("../static/data/", import.meta.url);
  const index = JSON.parse(await readFile(new URL("index.json", root), "utf8"));
  const entry = index.series.find(item => item.id === "2026-2027");
  const store = createPreviewStore(new URL("index.json", root).href, async url => ({
    ok: true, status: 200,
    json: async () => JSON.parse(await readFile(new URL(url), "utf8")),
  }));
  const previews = await store.getPreviews(entry);
  assert.deepEqual(previews.map(p => p.id), ["icpc-2026-preliminary-1", "icpc-2026-preliminary-2"]);
  const second = previews[1];
  assert.equal(previews[0].ratingAggregation, undefined);
  assert.equal(second.ratingAggregation, "normalized-lse");
  assert.deepEqual(second.metricSources.map(s => s.id), [
    "xcpcrating", "xcpcElo", "previousSeason", "currentSeason", "cpcfinder",
  ]);
  assert.equal(previews[0].metricSources.length, 4);
  const power = buildPreviewPower(second.teams, second.metricSources.map(s => s.id));
  assert.ok([...power.values()].every(p => p.counts.length === 6));
  assert.equal(second.teams.length, 2636);
  assert.equal(second.matchingSummary.members, 7788);
  assert.equal(second.sourceSnapshots.xcpcrating, "2026-09-06T16:17:41.538314+00:00");
  assert.equal(second.sourceSnapshots.xcpcElo, "2026-09-11T05:22:39.085Z");
  for (const [metric, expected] of [["xcpcrating", 7189], ["xcpcElo", 7155]]) {
    assert.equal(second.matchingSummary[metric], expected);
    assert.equal(second.teams.flatMap(t => t.members).filter(m => m.ratings[metric] !== null).length, expected);
  }
  assert.equal(second.sortAt, "2026-09-12T13:00:00+08:00");
  assert.equal(second.teamSource.url, "https://uep.pintia.cn/icpc-reg/examGroups/2086691546024431616/publicTeams");
  const url = writePreviewQuery("https://example.test/sub/?series=2026-2027", {
    view: "preview", contest: second.id,
  });
  assert.equal(readPreviewQuery(url).previewContest, second.id);
});

test("current season ratings break power ties and preserve missing and equal ratings", () => {
  const metrics = ["xcpcrating", "xcpcElo", "previousSeason", "currentSeason", "cpcfinder"];
  const teams = [1600, 1600, 1400, null].map((currentSeason, i) => ({
    id: String(i), sourceIndex: i, school: "学校",
    ratings: { xcpcrating: 1500, xcpcElo: 1500, previousSeason: 1500, currentSeason, cpcfinder: 10 },
    medals: { gold: 0, silver: 0, bronze: 0 },
  }));
  const oldPower = buildPreviewPower(teams, metrics.filter(id => id !== "currentSeason"));
  assert.deepEqual([...oldPower.values()].map(p => p.rank), [1, 1, 1, 1]);
  const power = buildPreviewPower(teams, metrics);
  assert.deepEqual([...power.values()].map(p => p.rank), [1, 1, 3, 4]);
  assert.deepEqual(power.get("0").counts, [0, 0, 0, 2, 0, 0]);
  assert.deepEqual(power.get("0").vector, [2, 0, 0, 0, 0, 0]);
  assert.deepEqual(sortPreviewTeams(teams, "currentSeason", "asc").map(t => t.id), ["2", "0", "1", "3"]);
  const ranks = buildPreviewRanks(teams, metrics);
  assert.deepEqual(teams.map(t => ranks.get(t.id).ratings.currentSeason), [1, 1, 3, null]);
});

test("preview and review default to the latest timestamp and preserve explicit contest links", async () => {
  const source = await readFile(new URL("../static/js/app.mjs", import.meta.url), "utf8");
  const select = runInNewContext(
    `${source.match(/function selectLatestContest\([^]*?\n\}/)[0]}\nselectLatestContest`,
  );
  for (const key of ["sortAt", "startAt"]) {
    const old = { id: "old", [key]: "2026-09-06T13:00:00+08:00" };
    const newest = { id: "new", [key]: "2026-09-12T13:00:00+08:00" };
    const middle = { id: "middle", [key]: "2026-09-12T04:00:00Z" };
    const contests = [newest, old, middle];
    assert.equal(select(contests, "", key), newest);
    assert.equal(select(contests, "missing", key), newest);
    assert.equal(select(contests, "old", key), old);
    assert.equal(select([old], undefined, key), old);
    assert.equal(select([], undefined, key), null);
    const tied = { id: "a", [key]: "2026-09-12T05:00:00Z" };
    assert.equal(select([newest, tied], undefined, key), tied);
    assert.deepEqual(contests, [newest, old, middle]);
  }
});

test("review preview selection does not overwrite the remembered preview contest", async () => {
  const source = await readFile(new URL("../static/js/app.mjs", import.meta.url), "utf8");
  const functions = ["selectLatestContest", "choosePreview"].map(name =>
    source.match(new RegExp(`function ${name}\\([^]*?\\n\\}`))[0],
  ).join("\n");
  const old = { id: "old", sortAt: "2026-09-06", teams: [], metricSources: [] };
  const newest = { id: "new", sortAt: "2026-09-12", teams: [], metricSources: [] };
  const state = { previews: [old, newest] };
  const choose = runInNewContext(`${functions}\nchoosePreview`, {
    state, buildPreviewPower, buildPreviewRanks,
  });
  choose();
  assert.equal(state.previewContestId, "new");
  choose("old");
  choose("new", false);
  assert.equal(state.preview.id, "new");
  assert.equal(state.previewContestId, "old");
  choose(state.previewContestId);
  assert.equal(state.preview, old);
});

test("unawarded IOI rows show only the competition without separators", async () => {
  const source = await readFile(new URL("../static/js/app.mjs", import.meta.url), "utf8");
  const render = runInNewContext(
    `${source.match(/function achievementRow\([^]*?\n\}/)[0]}\nachievementRow`,
    { achievementDisplayParts, node: (tag, properties, children = []) => ({ ...properties, children }) },
  );
  const row = render({ competition: "ioi", year: 2024, medal: "participant" });
  assert.equal(row.children.length, 1);
  assert.equal(row.children[0].text, "2024 IOI");
});

test("formats all preview ratings with exactly two decimals and preserves missing values", async () => {
  const source = await readFile(new URL("../static/js/app.mjs", import.meta.url), "utf8");
  const functions = ["formatPreviewRating", "previewRatingNode"].map((name) => {
    const match = source.match(new RegExp(`function ${name}\\([^]*?\\n\\}`));
    assert.ok(match);
    return match[0];
  }).join("\n");
  const render = runInNewContext(`${functions}\npreviewRatingNode`, {
    node: (tag, properties, children = []) => ({
      ...properties, text: properties.text ?? children.map(child => child.text).join(""),
    }),
    ratingNode: (value, className, text) => ({ text, classList: { remove() {}, add() {} } }),
    document: { createTextNode: text => ({ text }) },
  });
  for (const [value, text] of [[0, "0.00"], [1234, "1234.00"], [12.3, "12.30"], [12.345, "12.35"], [null, "—"]]) {
    for (const id of ["xcpcrating", "xcpcElo", "previousSeason", "currentSeason", "cpcfinder"]) {
      assert.equal(render(id, value).text, text);
    }
  }
  assert.equal(render("xcpcrating", 100).text, "100.00");
  assert.equal(render("xcpcElo", 2300).text, "2300.00");
  assert.equal(render("xcpcElo", 3000).text, "3000.00");
  assert.equal(render("xcpcElo", 3012.345).text, "3012.35");
  for (const id of ["xcpcElo", "previousSeason", "currentSeason"]) {
    for (const value of [0, 1400, 2300, 3000]) {
      assert.equal(render(id, value, true).text, String(value));
      assert.equal(render(id, value).text, `${value}.00`);
    }
    assert.equal(render(id, null, true).text, "—");
    assert.equal(render(id, 1400.125, true).text, "1400.13");
  }
  for (const id of ["xcpcrating", "cpcfinder"]) {
    assert.equal(render(id, 1400, true).text, "1400.00");
    assert.equal(render(id, 0, true).text, "0.00");
  }
});

function fixture() {
  const metricSources = [
    { id: "xcpcrating", title: "XCPC Rating", url: "https://example.test/rating" },
    { id: "xcpcElo", title: "XCPC Elo", url: "https://example.test/elo" },
    { id: "previousSeason", title: "上赛季 Rating", url: "https://example.test/previous" },
    { id: "cpcfinder", title: "CPC Finder", url: "https://example.test/finder" },
  ];
  const member = (name, xcpcrating, xcpcElo, gold = 0, silver = 0, bronze = 0) => ({
    name,
    achievements: [],
    ratings: {
      xcpcrating,
      xcpcElo,
      previousSeason: xcpcrating,
      cpcfinder: xcpcElo,
    },
    medals: { gold, silver, bronze },
  });
  return {
    schemaVersion: 1,
    seriesId: "2026-2027",
    seriesTitle: "2026–2027 ICPC + CCPC",
    id: "online-1",
    title: "网络赛一",
    sortAt: "2026-09-06T13:00:00+08:00",
    snapshotDate: "2026-09-04",
    teamSource: { title: "报名系统", url: "https://example.test/teams", note: "静态快照" },
    metricSources,
    matchingPolicy: "先姓名后学校",
    teams: [
      {
        id: "a",
        sourceIndex: 0,
        school: "甲大学",
        name: "Alpha",
        members: [member("甲", 1500, null, 1, 0, 2), member("乙", 1700, 1400, 0, 3, 0)],
        ratings: {
          xcpcrating: 1700,
          xcpcElo: 1400,
          previousSeason: 1700,
          cpcfinder: 1400,
        },
        medals: { gold: 1, silver: 3, bronze: 2 },
      },
      {
        id: "b",
        sourceIndex: 1,
        school: "乙大学",
        name: "Beta",
        members: [member("丙", null, 1800, 1, 1, 9)],
        ratings: {
          xcpcrating: null,
          xcpcElo: 1800,
          previousSeason: null,
          cpcfinder: 1800,
        },
        medals: { gold: 1, silver: 1, bronze: 9 },
      },
    ],
  };
}

test("renders the compact preview table without snapshot prose or hint icons", async () => {
  const [indexHtml, stylesheet, appModule] = await Promise.all([
    readFile(new URL("../static/index.html", import.meta.url), "utf8"),
    readFile(new URL("../static/styles.css", import.meta.url), "utf8"),
    readFile(new URL("../static/js/app.mjs", import.meta.url), "utf8"),
  ]);

  assert.match(indexHtml, /id="preview-team-source"/);
  assert.match(indexHtml, /id="preview-metric-sources"/);
  assert.match(indexHtml, /id="preview-contest-select"/);
  assert.doesNotMatch(indexHtml, /id="achievement-filter"/);
  assert.doesNotMatch(indexHtml, /id="achievement-options"/);
  assert.match(indexHtml, /学校排名随表格当前排序方式变化。NOI\/IOI成绩仅按姓名匹配，可能存在重名情况。/);
  assert.doesNotMatch(indexHtml, /id="preview-(?:summary|note)"/);
  assert.doesNotMatch(stylesheet, /ⓘ|cursor:\s*help/);
  assert.match(stylesheet, /\.table-shell\s*\{[^}]*container-type:\s*inline-size/);
  assert.match(stylesheet, /\.preview-table\s*\{[^}]*--preview-school-width:\s*min\(200px, 24cqw\)/);
  assert.match(stylesheet, /\.preview-table\s*\{[^}]*--preview-team-width:\s*min\(170px, calc\(40cqw - var\(--preview-school-width\)\)\)/);
  assert.match(stylesheet, /\.preview-table td:nth-child\(3\)[^{]*\{[^}]*position:\s*sticky/);
  assert.match(stylesheet, /\.preview-table \.table-sort-button\s*\{[^}]*justify-content:\s*center/);
  assert.match(stylesheet, /\.preview-school-content\s*\{[^}]*grid-template-columns:\s*1\.9rem minmax\(0, 1fr\)/);
  assert.doesNotMatch(stylesheet, /\.preview-school-cell\s*\{[^}]*display:\s*grid/);
  assert.match(stylesheet, /\.preview-table td\.preview-school-cell\s*\{[^}]*padding-right:\s*\.45rem;[^}]*padding-left:\s*\.45rem/);
  assert.match(stylesheet, /width:\s*calc\(var\(--preview-non-frozen-width\) \+ var\(--preview-school-width\) \+ var\(--preview-team-width\)\)/);
  assert.match(stylesheet, /\.preview-table th:nth-child\(2\)[^{]*\{[^}]*left:\s*var\(--preview-school-width\)/);
  assert.match(stylesheet, /@container \(max-width:\s*1120px\)[\s\S]*\.preview-table tbody td:nth-child\(3\)[^{]*\{[^}]*position:\s*static/);
  assert.match(stylesheet, /@container \(max-width:\s*600px\)[\s\S]*\.preview-table col:nth-child\(1\)[^{]*\{[^}]*display:\s*none/);
  assert.doesNotMatch(stylesheet, /@container \(max-width:\s*600px\)[\s\S]*\.preview-table col:nth-child\(3\)[^{]*\{[^}]*display:\s*none/);
  assert.match(stylesheet, /\.preview-table th:nth-child\(2\)[^{]*\{[^}]*left:\s*0/);
  assert.match(stylesheet, /\.preview-team-identity\s*,\s*\.identity-primary\s*\{[^}]*text-overflow:\s*ellipsis/);
  assert.match(stylesheet, /\.preview-rating-xcpcrating\s*\{[^}]*color:/);
  assert.match(stylesheet, /\.preview-rating-xcpc-elo\.rating-orange\s*\{[^}]*#ff8c00/);
  assert.match(stylesheet, /\.preview-rating-xcpc-elo-legendary\s*\{[^}]*#ff0000/);
  assert.match(stylesheet, /\.preview-rating-xcpc-elo-first\s*\{[^}]*#000000/);
  assert.match(stylesheet, /\.preview-achievement-list\s*\{[^}]*grid-template-columns:/);
  assert.match(stylesheet, /\.preview-member-name\.has-noi::after/);
  assert.match(stylesheet, /\.preview-member-name\.has-ioi::before/);
  assert.match(stylesheet, /\.preview-member-name::before[^}]*height:\s*3px/);
  assert.match(stylesheet, /\.preview-member-name\.has-noi::after[^}]*bottom:\s*-5px/);
  assert.match(stylesheet, /\.preview-member-name\.has-ioi::before[^}]*bottom:\s*-10px/);
  assert.match(stylesheet, /\.preview-member-name\.noi-gold[^}]*#d6a800/);
  assert.match(stylesheet, /\.preview-member-name\.ioi-participant[^}]*#57514d/);
  assert.match(stylesheet, /\.preview-ranked-value\s*\{[^}]*grid-template-columns:\s*minmax\(0, 1fr\) 1\.9rem/);
  assert.match(stylesheet, /\.preview-global-rank\s*\{[^}]*font-variant-numeric:\s*tabular-nums/);
  assert.match(stylesheet, /\.preview-member-tooltip\s*\{[^}]*position:\s*fixed/);
  assert.match(stylesheet, /\.preview-power-tooltip\s*\{[^}]*position:\s*fixed/);
  assert.match(stylesheet, /\.preview-power-shape\s*\{/);
  assert.match(appModule, /useGrouping:\s*false/);
  assert.match(appModule, /const value = team\.ratings\[source\.id\];/);
  assert.match(appModule, /\(member\) => member\.ratings\[source\.id\]/);
  assert.doesNotMatch(appModule, /previewRatingValue/);
  assert.match(appModule, /renderValue\(memberValue\(member\), true\)/);
  assert.match(appModule, /elements\.seriesModeSwitch\.hidden = supportedCount === 0/);
  assert.match(appModule, /renderSourceLinks\(elements\.previewTeamSource, "名单来源："/);
  assert.match(appModule, /renderSourceLinks\(elements\.previewMetricSources, "数据来源："/);
  assert.match(appModule, /elements\.previewContestSelect\.replaceChildren/);
  assert.match(appModule, /const widths = \[200, 170, 190, 96,/);
  assert.match(appModule, /table\.style\.setProperty\("--preview-table-width"/);
  assert.match(appModule, /table\.style\.setProperty\("--preview-non-frozen-width"/);
  assert.doesNotMatch(appModule, /table\.style\.setProperty\("--preview-data-width"/);
  assert.match(appModule, /className: "preview-team-identity"/);
  assert.match(appModule, /className: "identity-secondary"/);
  assert.match(appModule, /`#\$\{schoolRank\} `.*\$\{team\.school\}/);
  assert.doesNotMatch(appModule, /校排 #\$\{schoolRank\}/);
  assert.match(appModule, /attachPreviewTooltip\(identityControl, identityTooltip\)/);
  assert.match(appModule, /function previewMemberControl\(member\)/);
  assert.match(appModule, /memberChildren\.push\(previewMemberControl\(member\)\)/);
  assert.match(appModule, /previewSortHeader\("奖牌（三人总和）", "medals"\)/);
  assert.doesNotMatch(appModule, /奖牌（🥇\/🥈\/🥉）/);
  assert.match(appModule, /function positionPreviewTooltip\(/);
  assert.match(appModule, /document\.body\.append\(tooltip\)/);
  assert.doesNotMatch(appModule, /排序元组：|preview-power-vector/);
});

test("published 2026-2027 preview satisfies its schema", async () => {
  const document = JSON.parse(await readFile(
    new URL("../static/data/previews/2026-2027.json", import.meta.url),
    "utf8",
  ));
  assert.equal(validatePreview(document), document);
  assert.equal(document.teams.length, 2535);
  assert.ok(document.teams.every((team) => team.members.length > 0));
});

test("preview tooltips hide immediately on mouse leave and preserve keyboard focus", async () => {
  const app = await readFile(new URL("../static/js/app.mjs", import.meta.url), "utf8");
  const source = app.slice(app.indexOf("function attachPreviewTooltip("), app.indexOf("function previewMedalNode("));
  const events = new Map();
  const control = { addEventListener: (name, callback) => events.set(name, callback) };
  let visible = false;
  const tooltip = {
    classList: { add: () => { visible = true; }, remove: () => { visible = false; } },
    remove() {},
  };
  const attach = new Function("document", "positionPreviewTooltip",
    `let activePreviewTooltip = null; ${source}; return attachPreviewTooltip;`)(
    { body: { append() {} } }, () => {},
  );
  attach(control, tooltip);
  events.get("mouseenter")();
  assert.equal(visible, true);
  events.get("mouseleave")();
  assert.equal(visible, false);
  events.get("focus")();
  assert.equal(visible, true);
  events.get("blur")();
  assert.equal(visible, false);
});

test("history tooltip omits the member list and aligns ranks in shared columns", async () => {
  const [app, css] = await Promise.all([
    readFile(new URL("../static/js/app.mjs", import.meta.url), "utf8"),
    readFile(new URL("../static/styles.css", import.meta.url), "utf8"),
  ]);
  assert.doesNotMatch(app, /preview-history-members/);
  assert.doesNotMatch(css, /\.preview-history-tooltip\s*\{[^}]*pointer-events:\s*auto/);
  assert.match(app, /team\.previousSeasonHistory \? "暂无" :/);
  assert.match(css, /\.preview-history-tooltip\s*\{[^}]*grid-template-columns:/);
  assert.match(css, /\.preview-history-tooltip > span\.preview-history-row\s*\{[^}]*grid-template-columns:\s*subgrid/);
  assert.match(css, /\.preview-history-rank\s*\{[^}]*text-align:\s*right;[^}]*font-variant-numeric:\s*tabular-nums/);
});

test("validates team history and abbreviates regional and final titles", async () => {
  const { previewHistoryTitle } = await import("../static/js/preview.mjs");
  const record = {
    contestId: "icpc2025chengdu", contestTitle: "第 50 届 ICPC 国际大学生程序设计竞赛区域赛成都站",
    startAt: "2025-10-26T09:10:00+08:00", teamId: "old", teamName: "历史队名",
    rank: 1, medal: "gold", matchedMembers: 2,
  };
  const document = fixture();
  document.teams[0].previousSeasonHistory = [record];
  assert.equal(validatePreview(document), document);
  assert.equal(previewHistoryTitle(record), "50th ICPC 成都");
  assert.equal(previewHistoryTitle({ contestId: "ccpc2025final", contestTitle: "第十一届中国大学生程序设计竞赛总决赛" }), "11th CCPC Final");
  assert.equal(previewHistoryTitle({ contestId: "icpc2025hongkong", contestTitle: "The 50th ICPC Asia Hong Kong Regional Contest" }), "50th ICPC 香港");
  for (const [field, value, error] of [
    ["rank", 0, /rank/], ["medal", "unknown", /medal/],
    ["matchedMembers", 3, /matched members/], ["startAt", "invalid", /startAt/],
  ]) {
    const broken = structuredClone(document);
    broken.teams[0].previousSeasonHistory[0][field] = value;
    assert.throws(() => validatePreview(broken), error);
  }
  const duplicate = structuredClone(document);
  duplicate.teams[0].previousSeasonHistory.push(record);
  assert.throws(() => validatePreview(duplicate), /duplicate history/);
});

test("normalized LSE preserves scale, favors strong members and validates per snapshot", () => {
  assert.equal(normalizedLseRating([]), null);
  assert.equal(normalizedLseRating([2000, 2000, 2000]), 2000);
  assert.equal(normalizedLseRating([1400]), 1400);
  assert.ok(Math.abs(normalizedLseRating([2000, 1600, 1600]) - 1840.823996531185) < 1e-9);
  assert.ok(Math.abs(normalizedLseRating([102000, 101600, 101600]) - 101840.823996531185) < 1e-9);
  for (const value of [null, true, NaN, Infinity, "1400"]) {
    assert.throws(() => normalizedLseRating([value]), /finite number/);
  }
  const document = fixture();
  document.ratingAggregation = "normalized-lse";
  for (const team of document.teams) {
    for (const { id } of document.metricSources) {
      if (id !== "cpcfinder") team.ratings[id] = normalizedLseRating(
        team.members.map(member => member.ratings[id]).filter(value => value !== null),
      );
    }
  }
  assert.equal(validatePreview(document), document);
  assert.equal(document.teams[0].ratings.xcpcElo, 1400);
  assert.equal(document.teams[0].ratings.cpcfinder, 1400);
  const broken = structuredClone(document);
  broken.teams[0].ratings.xcpcrating = 1700;
  assert.throws(() => validatePreview(broken), /normalized LSE/);
  const invalidMode = structuredClone(document);
  invalidMode.ratingAggregation = "average";
  assert.throws(() => validatePreview(invalidMode), /unsupported aggregation/);
  const nullMode = structuredClone(document);
  nullMode.ratingAggregation = null;
  assert.throws(() => validatePreview(nullMode), /unsupported aggregation/);
});

test("validates legacy member maxima and team medal totals", () => {
  const document = fixture();
  assert.equal(validatePreview(document), document);
  const brokenRating = structuredClone(document);
  brokenRating.teams[0].ratings.xcpcrating = 1500;
  assert.throws(() => validatePreview(brokenRating), /highest member value/);
  const brokenMedals = structuredClone(document);
  brokenMedals.teams[0].medals.bronze = 1;
  assert.throws(() => validatePreview(brokenMedals), /member total/);
});

test("validates achievement history and selects each competition's best medal", () => {
  const document = fixture();
  const achievements = [
    { competition: "noi", year: 2024, medal: "silver", rank: 20, score: 500, maxScore: 705 },
    { competition: "noi", year: 2025, medal: "gold", rank: 1, score: 600, maxScore: 705 },
    { competition: "ioi", year: 2025, medal: "bronze", rank: 100, score: 200, maxScore: 600 },
    { competition: "ioi", year: 2026, medal: "participant" },
  ];
  document.teams[0].members[0].achievements = achievements;

  assert.equal(validatePreview(document), document);
  assert.equal(bestAchievementMedal(achievements, "noi"), "gold");
  assert.equal(bestAchievementMedal(achievements, "ioi"), "bronze");
  assert.equal(bestAchievementMedal([], "noi"), null);
  assert.deepEqual(achievementDisplayParts(achievements[0]), ["2024 NOI", "银牌#20", "500 / 705"]);
  assert.deepEqual(achievementDisplayParts(achievements[2]), ["2025 IOI", "铜牌#100", "200 / 600"]);
  assert.deepEqual(achievementDisplayParts(achievements[3]), ["2026 IOI"]);

  const wrongOrder = fixture();
  wrongOrder.teams[0].members[0].achievements = [achievements[2], achievements[0]];
  assert.throws(() => validatePreview(wrongOrder), /must be chronological/);
});

test("searches school, team and all member names", () => {
  const teams = fixture().teams;
  assert.deepEqual(searchPreviewTeams(teams, "Alpha 乙").map(({ id }) => id), ["a"]);
  assert.deepEqual(searchPreviewTeams(teams, "", ["乙大学"]).map(({ id }) => id), ["b"]);
});

test("sorts nullable ratings last and medals by gold, silver, bronze", () => {
  const teams = fixture().teams;
  assert.deepEqual(sortPreviewTeams(teams, "xcpcrating", "desc").map(({ id }) => id), ["a", "b"]);
  assert.deepEqual(sortPreviewTeams(teams, "xcpcElo", "desc").map(({ id }) => id), ["b", "a"]);
  assert.deepEqual(sortPreviewTeams(teams, "medals", "desc").map(({ id }) => id), ["a", "b"]);
});

test("breaks equal sort keys by school ascending", () => {
  const teams = fixture().teams.map((team, index) => ({
    ...team,
    id: index ? "school-a" : "school-b",
    sourceIndex: index,
    school: index ? "A大学" : "B大学",
    name: "同名队伍",
    members: [{ name: "同名成员" }],
    ratings: Object.fromEntries(Object.keys(team.ratings).map((metricId) => [metricId, 2000])),
    medals: { gold: 1, silver: 1, bronze: 1 },
  }));

  assert.deepEqual(sortPreviewTeams(teams, "xcpcrating", "desc").map(({ id }) => id), ["school-a", "school-b"]);
  assert.deepEqual(sortPreviewTeams(teams, "xcpcrating", "asc").map(({ id }) => id), ["school-a", "school-b"]);
  assert.deepEqual(sortPreviewTeams(teams, "medals", "desc").map(({ id }) => id), ["school-a", "school-b"]);
  assert.deepEqual(sortPreviewTeams(teams, "name", "desc").map(({ id }) => id), ["school-a", "school-b"]);
  assert.deepEqual(sortPreviewTeams(teams, "members", "desc").map(({ id }) => id), ["school-a", "school-b"]);
  const power = buildPreviewPower(teams);
  const powerSorted = sortPreviewTeams(teams, "power", "desc", power);
  assert.deepEqual(powerSorted.map(({ id }) => id), ["school-a", "school-b"]);
  assert.deepEqual([...buildPreviewSchoolRanks(powerSorted, "power", power)], [["school-a", 1], ["school-b", 1]]);
  assert.deepEqual(
    [...buildPreviewSchoolRanks(sortPreviewTeams(teams, "medals"), "medals")],
    [["school-a", 1], ["school-b", 1]],
  );
});

test("ranks tied schools from the unfiltered current preview order", () => {
  const makeTeam = (id, sourceIndex, school, score) => ({
    id,
    sourceIndex,
    school,
    name: id,
    members: [{ name: id }],
    ratings: { score },
    medals: { gold: 0, silver: 0, bronze: 0 },
  });
  const teams = [
    makeTeam("a-low", 0, "A大学", 10),
    makeTeam("c-best", 1, "C大学", 30),
    makeTeam("b-best", 2, "B大学", 30),
    makeTeam("b-also-tied", 3, "B大学", 30),
    makeTeam("a-best", 4, "A大学", 20),
  ];
  const sorted = sortPreviewTeams(teams, "score", "desc");
  const ranks = buildPreviewSchoolRanks(sorted, "score");

  assert.deepEqual(sorted.map(({ id }) => id), ["b-best", "b-also-tied", "c-best", "a-best", "a-low"]);
  assert.deepEqual([...ranks], [["b-best", 1], ["c-best", 1], ["a-best", 3]]);
  assert.equal(ranks.has("b-also-tied"), false);
  assert.equal(ranks.has("a-low"), false);
  assert.deepEqual(
    searchPreviewTeams(sorted, "a-low").map((team) => [team.id, ranks.get(team.id) ?? null]),
    [["a-low", null]],
  );
  assert.deepEqual(buildPreviewSchoolRanks(sorted, "school"), new Map());
  assert.deepEqual(buildPreviewSchoolRanks(sorted, "name"), new Map());
  assert.deepEqual(buildPreviewSchoolRanks(sorted, "members"), new Map());
});

test("ranks comprehensive power by a descending five-value dominance tuple", () => {
  const teams = fixture().teams;
  const metricIds = ["xcpcrating", "xcpcElo", "previousSeason", "cpcfinder"];
  const power = buildPreviewPower(teams, metricIds);

  assert.deepEqual(power.get("a"), {
    counts: [1, 0, 1, 0, 1],
    vector: [1, 1, 1, 0, 0],
    rank: 1,
  });
  assert.deepEqual(power.get("b"), {
    counts: [0, 1, 0, 1, 0],
    vector: [1, 1, 0, 0, 0],
    rank: 2,
  });
  assert.deepEqual(
    sortPreviewTeams(teams, "power", "desc", power).map(({ id }) => id),
    ["a", "b"],
  );
});

test("ranks each displayed metric globally with competition ties", () => {
  const document = fixture();
  const metricIds = document.metricSources.map(({ id }) => id);
  const ranks = buildPreviewRanks(document.teams, metricIds);

  assert.deepEqual(ranks.get("a"), {
    ratings: { xcpcrating: 1, xcpcElo: 2, previousSeason: 1, cpcfinder: 2 },
    medals: 1,
  });
  assert.deepEqual(ranks.get("b"), {
    ratings: { xcpcrating: null, xcpcElo: 1, previousSeason: null, cpcfinder: 1 },
    medals: 2,
  });

  const tied = structuredClone(document.teams[0]);
  tied.id = "c";
  tied.sourceIndex = 2;
  const tiedRanks = buildPreviewRanks([...document.teams, tied], metricIds);
  assert.equal(tiedRanks.get("a").ratings.xcpcrating, 1);
  assert.equal(tiedRanks.get("c").ratings.xcpcrating, 1);
  assert.equal(tiedRanks.get("b").ratings.xcpcElo, 1);
  assert.equal(tiedRanks.get("a").ratings.xcpcElo, 2);
  assert.equal(tiedRanks.get("c").ratings.xcpcElo, 2);
});

test("ranks zero CPC Finder scores but ties them with missing values only for power", () => {
  const teams = [
    {
      id: "scored",
      sourceIndex: 0,
      school: "A大学",
      ratings: { cpcfinder: 100 },
      medals: { gold: 0, silver: 0, bronze: 0 },
    },
    {
      id: "zero",
      sourceIndex: 1,
      school: "B大学",
      ratings: { cpcfinder: 0 },
      medals: { gold: 0, silver: 0, bronze: 0 },
    },
    {
      id: "missing",
      sourceIndex: 2,
      school: "A大学",
      ratings: { cpcfinder: null },
      medals: { gold: 0, silver: 0, bronze: 0 },
    },
  ];

  assert.equal(previewRatingValue("cpcfinder", 0), null);
  assert.equal(previewRatingValue("xcpcElo", 0), 0);
  assert.deepEqual(buildPreviewRanks(teams, ["cpcfinder"]), new Map([
    ["scored", { ratings: { cpcfinder: 1 }, medals: 1 }],
    ["zero", { ratings: { cpcfinder: 2 }, medals: 1 }],
    ["missing", { ratings: { cpcfinder: null }, medals: 1 }],
  ]));
  assert.deepEqual(
    sortPreviewTeams(teams, "cpcfinder", "desc").map(({ id }) => id),
    ["scored", "zero", "missing"],
  );
  const power = buildPreviewPower(teams, ["cpcfinder"]);
  assert.deepEqual(
    sortPreviewTeams(teams, "cpcfinder", "asc").map(({ id }) => id),
    ["zero", "scored", "missing"],
  );
  const tiedZero = { ...teams[1], id: "zero-tie", sourceIndex: 3, school: "D大学" };
  const ranks = buildPreviewRanks([...teams, tiedZero], ["cpcfinder"]);
  assert.equal(ranks.get("zero").ratings.cpcfinder, 2);
  assert.equal(ranks.get("zero-tie").ratings.cpcfinder, 2);
  assert.deepEqual(power.get("scored").counts, [2, 0]);
  assert.deepEqual(power.get("zero").counts, [0, 0]);
  assert.deepEqual(power.get("zero"), power.get("missing"));
  assert.equal(power.get("zero").rank, power.get("missing").rank);
});

test("comprehensive power treats missing ratings as weakest and preserves ties", () => {
  const metricIds = ["xcpcrating", "xcpcElo", "previousSeason", "cpcfinder"];
  const makeTeam = (id, sourceIndex, value) => ({
    id,
    sourceIndex,
    ratings: Object.fromEntries(metricIds.map((metricId) => [metricId, value])),
    medals: { gold: 0, silver: 0, bronze: 0 },
  });
  const teams = [makeTeam("a", 0, 10), makeTeam("b", 1, 10), makeTeam("c", 2, null)];

  const power = buildPreviewPower(teams, metricIds);

  assert.deepEqual(power.get("a"), {
    counts: [1, 1, 1, 1, 0],
    vector: [1, 1, 1, 1, 0],
    rank: 1,
  });
  assert.deepEqual(power.get("b"), power.get("a"));
  assert.equal(power.get("c").rank, null);
});

test("power availability uses input data, not dominance counts, in five and six dimensions", () => {
  for (const metricIds of [
    ["xcpcrating", "xcpcElo", "previousSeason", "cpcfinder"],
    ["xcpcrating", "xcpcElo", "previousSeason", "currentSeason", "cpcfinder"],
  ]) {
    const makeTeam = (id, ratings = {}, medals = {}) => ({
      id, sourceIndex: 0, school: "学校",
      ratings: { ...Object.fromEntries(metricIds.map(id => [id, null])), ...ratings },
      medals: { gold: 0, silver: 0, bronze: 0, ...medals },
    });
    for (const team of [makeTeam("missing"), makeTeam("zero-cpc", { cpcfinder: 0 })]) {
      assert.equal(buildPreviewPower([team], metricIds).get(team.id).rank, null);
    }
    for (const team of [
      makeTeam("zero-rating", { xcpcElo: 0 }),
      makeTeam("scored", { [metricIds.at(-2)]: 1400 }),
      makeTeam("cpc-only", { cpcfinder: 10 }),
      makeTeam("medal-only", {}, { bronze: 1 }),
    ]) {
      const entry = buildPreviewPower([team], metricIds).get(team.id);
      assert.ok(entry.counts.every(count => count === 0));
      assert.equal(entry.rank, 1, "a valid score still ranks when no other team is beaten");
    }
  }
});

test("both published previews omit missing power controls and retain scored radar controls", async () => {
  const source = await readFile(new URL("../static/js/app.mjs", import.meta.url), "utf8");
  for (const path of ["2026-2027.json", "icpc-2026-preliminary-2.json"]) {
    const preview = JSON.parse(await readFile(new URL(`../static/data/previews/${path}`, import.meta.url), "utf8"));
    const metricIds = preview.metricSources.map(s => s.id);
    const power = buildPreviewPower(preview.teams, metricIds);
    let radars = 0;
    let tooltips = 0;
    const render = runInNewContext(
      `${source.match(/function previewPowerControl\([^]*?\n\}/)[0]}\npreviewPowerControl`, {
        state: { previewPower: power },
        node: (tag, properties, children = []) => ({ tag, ...properties, children }),
        document: { createTextNode: text => ({ text }) },
        previewPowerRadar: () => { radars++; return { tag: "svg" }; },
        attachPreviewTooltip: () => { tooltips++; },
      },
    );
    const missing = preview.teams.filter(t => metricIds.every(id => previewRatingValue(id, t.ratings[id]) === null)
      && Object.values(t.medals).every(value => value === 0));
    assert.ok(missing.length > 0);
    for (const team of missing) {
      assert.equal(power.get(team.id).rank, null);
      const control = render(team);
      assert.equal(control.text, "—");
      assert.equal(control.tabIndex, undefined);
      assert.equal(control.children.length, 0);
    }
    assert.equal(radars, 0);
    assert.equal(tooltips, 0);
    const scored = preview.teams.find(t => power.get(t.id).rank === 1);
    const control = render(scored);
    assert.equal(control.tabIndex, 0);
    assert.equal(control.children[0].text, "#1");
    assert.equal(radars, 1);
    assert.equal(tooltips, 1);
  }
});

test("round trips preview sorting through URL state", () => {
  const next = writePreviewQuery("https://example.test/?series=2026-2027", {
    view: "preview",
    sort: "medals",
    order: "asc",
  });
  assert.equal(next.searchParams.get("view"), "preview");
  assert.deepEqual(readPreviewQuery(next), {
    previewSort: "medals",
    previewOrder: "asc",
    previewContest: "",
  });
  assert.deepEqual(readPreviewQuery("https://example.test/"), {
    previewSort: "power",
    previewOrder: "desc",
    previewContest: "",
  });
  assert.equal(
    writePreviewQuery("https://example.test/?achievement=noi:gold", { view: "preview" })
      .searchParams.has("achievement"),
    false,
  );
});

test("loads preview relative to the site index", async () => {
  const document = fixture();
  const seen = [];
  const fetchImpl = async (url) => {
    seen.push(url);
    return { ok: true, status: 200, json: async () => document };
  };
  const store = createPreviewStore("https://example.test/sub/data/index.json", fetchImpl);
  const loaded = await store.getSeries({
    id: "2026-2027",
    previewPath: "previews/2026-2027.json",
  });
  assert.equal(loaded, document);
  assert.deepEqual(seen, ["https://example.test/sub/data/previews/2026-2027.json"]);
});
