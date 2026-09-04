import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  buildPreviewPower,
  buildPreviewRanks,
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
  assert.doesNotMatch(indexHtml, /id="preview-(?:summary|note)"/);
  assert.doesNotMatch(stylesheet, /ⓘ|cursor:\s*help/);
  assert.match(stylesheet, /\.preview-table\s*\{[^}]*width:\s*1214px/);
  assert.match(stylesheet, /\.preview-table td:nth-child\(3\)[^{]*\{[^}]*position:\s*sticky/);
  assert.match(stylesheet, /@media \(max-width:\s*700px\)[\s\S]*\.preview-table th:nth-child\(2\)[^{]*\{[^}]*left:\s*112px/);
  assert.match(stylesheet, /@media \(max-width:\s*700px\)[\s\S]*\.preview-table tbody td:nth-child\(3\)[^{]*\{[^}]*position:\s*static/);
  assert.match(stylesheet, /\.preview-rating-xcpcrating\s*\{[^}]*color:/);
  assert.match(stylesheet, /\.preview-rating-xcpc-elo\.rating-orange\s*\{[^}]*#ff8c00/);
  assert.match(stylesheet, /\.preview-rating-xcpc-elo-legendary\s*\{[^}]*#ff0000/);
  assert.match(stylesheet, /\.preview-rating-xcpc-elo-first\s*\{[^}]*#000000/);
  assert.match(stylesheet, /\.preview-member-tooltip > span\s*\{/);
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
      ratings: { cpcfinder: 100 },
      medals: { gold: 0, silver: 0, bronze: 0 },
    },
    {
      id: "zero",
      sourceIndex: 1,
      ratings: { cpcfinder: 0 },
      medals: { gold: 0, silver: 0, bronze: 0 },
    },
    {
      id: "missing",
      sourceIndex: 2,
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
  assert.deepEqual(readPreviewQuery(next), { previewSort: "medals", previewOrder: "asc" });
  assert.deepEqual(readPreviewQuery("https://example.test/"), {
    previewSort: "power",
    previewOrder: "desc",
  });
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
