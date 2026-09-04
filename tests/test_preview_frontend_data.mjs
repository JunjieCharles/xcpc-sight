import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  buildPreviewPower,
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
  assert.match(stylesheet, /\.preview-member-name\.ioi-participant[^}]*#111111/);
  assert.match(stylesheet, /\.preview-ranked-value\s*\{[^}]*grid-template-columns:\s*minmax\(0, 1fr\) 1\.9rem/);
  assert.match(stylesheet, /\.preview-global-rank\s*\{[^}]*font-variant-numeric:\s*tabular-nums/);
  assert.match(stylesheet, /\.preview-member-tooltip\s*\{[^}]*position:\s*fixed/);
  assert.match(stylesheet, /\.preview-power-tooltip\s*\{[^}]*position:\s*fixed/);
  assert.match(stylesheet, /\.preview-power-shape\s*\{/);
  assert.match(appModule, /useGrouping:\s*false/);
  assert.match(appModule, /formatPreviewRating\(value, sourceId === "xcpcrating" \? 2 : 0\)/);
  assert.match(appModule, /`🥇\$\{medals\.gold\}  🥈\$\{medals\.silver\}  🥉\$\{medals\.bronze\}`/);
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
  assert.match(appModule, /previewSortHeader\("奖牌", "medals"\)/);
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

test("validates member maxima and team medal totals", () => {
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
  assert.deepEqual(achievementDisplayParts(achievements[3]), ["2026 IOI", "参与#—", "未获奖"]);

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

test("treats a zero CPC Finder score as missing for display and ranking", () => {
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
      school: "C大学",
      ratings: { cpcfinder: null },
      medals: { gold: 0, silver: 0, bronze: 0 },
    },
  ];

  assert.equal(previewRatingValue("cpcfinder", 0), null);
  assert.equal(previewRatingValue("xcpcElo", 0), 0);
  assert.deepEqual(buildPreviewRanks(teams, ["cpcfinder"]), new Map([
    ["scored", { ratings: { cpcfinder: 1 }, medals: 1 }],
    ["zero", { ratings: { cpcfinder: null }, medals: 1 }],
    ["missing", { ratings: { cpcfinder: null }, medals: 1 }],
  ]));
  assert.deepEqual(
    sortPreviewTeams(teams, "cpcfinder", "desc").map(({ id }) => id),
    ["scored", "zero", "missing"],
  );
  const power = buildPreviewPower(teams, ["cpcfinder"]);
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
  assert.equal(power.get("c").rank, 3);
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
  });
  assert.deepEqual(readPreviewQuery("https://example.test/"), {
    previewSort: "power",
    previewOrder: "desc",
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
