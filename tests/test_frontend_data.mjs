import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  carriedRatings,
  clearJsonCache,
  createDataStore,
  fetchJson,
  formatDelta,
  indexSeries,
  ratingTier,
  ratingTimeline,
  readQueryState,
  resolveDataUrl,
  searchCompetitors,
  validateIndex,
  validateSeries,
  writeQueryState,
} from "../static/js/data.mjs";

test("versions cache-sensitive frontend assets consistently", async () => {
  const [indexHtml, appModule] = await Promise.all([
    readFile(new URL("../static/index.html", import.meta.url), "utf8"),
    readFile(new URL("../static/js/app.mjs", import.meta.url), "utf8"),
  ]);
  const stylesheetRevision = indexHtml.match(/styles\.css\?v=([\w-]+)/)?.[1];
  const applicationRevision = indexHtml.match(/app\.mjs\?v=([\w-]+)/)?.[1];

  assert.ok(stylesheetRevision);
  assert.equal(applicationRevision, stylesheetRevision);
  assert.match(appModule, new RegExp(`data\\.mjs\\?v=${applicationRevision}`));
});

function fixture() {
  return {
    schemaVersion: 1,
    id: "season",
    title: "Season",
    initialRating: 1400,
    contests: [
      { id: "a", title: "A", collection: "icpc", startAt: "2025-01-01T10:00:00+08:00" },
      { id: "b", title: "B", collection: "ccpc", startAt: "2025-01-02T10:00:00+08:00" },
      { id: "c", title: "C", collection: "icpc", startAt: "2025-01-03T10:00:00+08:00" },
    ],
    competitors: [{
      id: "c_1", rank: 1, school: "Example University", member: "Alice", finalRating: 1430,
      contestsParticipated: 2,
      participations: [
        { contestIndex: 0, contestRank: 2, before: 1400, delta: 20, after: 1420 },
        { contestIndex: 2, contestRank: 1, before: 1420, delta: 10, after: 1430 },
      ],
    }],
  };
}

test("validates and indexes a series once", () => {
  const series = fixture();
  assert.equal(validateSeries(series), series);
  assert.equal(validateSeries(series), series);
  const first = indexSeries(series);
  assert.equal(indexSeries(series), first);
  assert.equal(first.competitorById.get("c_1"), series.competitors[0]);
  assert.equal(first.participantsByContest[1].length, 0);
  assert.equal(first.participantsByContest[2][0].participation.after, 1430);
});

test("accepts an empty display school", () => {
  const document = fixture();
  document.competitors[0].school = "";
  assert.equal(validateSeries(document).competitors[0].school, "");
});

test("rejects broken rating continuity", () => {
  const series = fixture();
  series.competitors[0].participations[1].before = 1410;
  series.competitors[0].participations[1].delta = 20;
  assert.throws(() => validateSeries(series), /rating is not continuous/);
});

test("validates index references and resolves paths relative to it", () => {
  const index = { schemaVersion: 1, defaultSeriesId: "season", series: [{ id: "season", title: "Season", path: "series/season.json" }] };
  assert.equal(validateIndex(index), index);
  assert.equal(resolveDataUrl(index.series[0].path, "https://example.test/site/data/index.json"), "https://example.test/site/data/series/season.json");
  assert.throws(() => validateIndex({ ...index, defaultSeriesId: "missing" }), /does not reference/);
});

test("derives initial and carried ratings with participation state", () => {
  const series = fixture();
  assert.deepEqual(carriedRatings(series.competitors[0], 3, series.initialRating), [1420, 1420, 1430]);
  const timeline = ratingTimeline(series.competitors[0], series.contests, series.initialRating);
  assert.deepEqual(timeline.map(({ rating, participated }) => ({ rating, participated })), [
    { rating: 1420, participated: true },
    { rating: 1420, participated: false },
    { rating: 1430, participated: true },
  ]);
  assert.equal(formatDelta(12), "+12");
  assert.equal(formatDelta(0), "0");
  assert.equal(formatDelta(-8), "-8");
});

test("shows initial rating before debut and zero-delta participation explicitly", () => {
  const series = fixture();
  const competitor = {
    ...series.competitors[0],
    finalRating: 1400,
    contestsParticipated: 1,
    participations: [{ contestIndex: 1, contestRank: 3, before: 1400, delta: 0, after: 1400 }],
  };
  const timeline = ratingTimeline(competitor, series.contests, series.initialRating);
  assert.equal(timeline[0].rating, 1400);
  assert.equal(timeline[0].participated, false);
  assert.equal(timeline[1].rating, 1400);
  assert.equal(timeline[1].participated, true);
  assert.equal(timeline[1].participation.delta, 0);
  assert.equal(timeline[2].rating, 1400);
  assert.equal(timeline[2].participated, false);
});

test("classifies Codeforces-style rating boundaries", () => {
  const expected = [
    [1199, "rating-gray", "#808080", false], [1200, "rating-green", "#008000", false],
    [1399, "rating-green", "#008000", false], [1400, "rating-cyan", "#03a89e", false],
    [1599, "rating-cyan", "#03a89e", false], [1600, "rating-blue", "#0000ff", false],
    [1899, "rating-blue", "#0000ff", false], [1900, "rating-purple", "#aa00aa", false],
    [2099, "rating-purple", "#aa00aa", false], [2100, "rating-orange", "#ffc000", false],
    [2399, "rating-orange", "#ffc000", false], [2400, "rating-red", "#ff0000", false],
    [2999, "rating-red", "#ff0000", false], [3000, "rating-legendary", "#000000", true],
  ];
  for (const [rating, className, color, legendary] of expected) {
    assert.deepEqual(ratingTier(rating), { className, color, legendary });
  }
});

test("searches all terms across member and school", () => {
  const competitors = fixture().competitors;
  assert.equal(searchCompetitors(competitors, "alice university").length, 1);
  assert.equal(searchCompetitors(competitors, "alice missing").length, 0);
  assert.equal(searchCompetitors(competitors, "  "), competitors);
});

test("round trips URL state without dropping unrelated parameters", () => {
  const next = writeQueryState("https://example.test/site/?keep=1", { series: "season", query: "Alice 王", contest: "", competitor: "c_1" });
  assert.equal(next.searchParams.get("keep"), "1");
  assert.deepEqual(readQueryState(next), { series: "season", query: "Alice 王", contest: "", competitor: "c_1" });
});

test("caches in-flight JSON requests and evicts failures", async () => {
  clearJsonCache();
  let calls = 0;
  const requests = [];
  const fetchImpl = async (url, options) => { calls += 1; requests.push({ url, options }); return { ok: true, json: async () => ({ value: 1 }) }; };
  const one = fetchJson("https://example.test/data.json", fetchImpl);
  const two = fetchJson("https://example.test/data.json", fetchImpl);
  assert.equal(one, two);
  assert.deepEqual(await one, { value: 1 });
  assert.equal(calls, 1);
  assert.deepEqual(requests, [{ url: "https://example.test/data.json", options: { cache: "no-cache" } }]);

  clearJsonCache();
  const failing = async () => { calls += 1; return { ok: false, status: 500 }; };
  await assert.rejects(fetchJson("https://example.test/fail.json", failing), /500/);
  await assert.rejects(fetchJson("https://example.test/fail.json", failing), /500/);
  assert.equal(calls, 3);
});

test("data store preserves index order and loads any series by ID", async () => {
  clearJsonCache();
  const nowcoder = { ...fixture(), id: "nowcoder-summer-2026", title: "2026牛客暑期多校训练营" };
  const hdu = {
    ...fixture(),
    id: "hdu-summer-2026",
    title: "2026“钉耙编程”中国大学生算法设计暑期联赛",
  };
  const index = {
    schemaVersion: 1,
    defaultSeriesId: "nowcoder-summer-2026",
    series: [
      { id: "nowcoder-summer-2026", title: nowcoder.title, path: "series/nowcoder-summer-2026.json" },
      { id: "hdu-summer-2026", title: hdu.title, path: "series/hdu-summer-2026.json" },
      { id: "season", title: "Season", path: "series/season.json" },
    ],
  };
  const responses = new Map([
    ["https://example.test/sub/data/index.json", index],
    ["https://example.test/sub/data/series/nowcoder-summer-2026.json", nowcoder],
    ["https://example.test/sub/data/series/hdu-summer-2026.json", hdu],
    ["https://example.test/sub/data/series/season.json", fixture()],
  ]);
  const fetchImpl = async (url) => ({ ok: responses.has(url), status: responses.has(url) ? 200 : 404, json: async () => responses.get(url) });
  const store = createDataStore("https://example.test/sub/data/index.json", fetchImpl);
  const loadedIndex = await store.getIndex();
  assert.deepEqual(loadedIndex.series.map(({ id }) => id), ["nowcoder-summer-2026", "hdu-summer-2026", "season"]);
  const loaded = await store.getSeries("hdu-summer-2026");
  assert.equal(loaded.series.id, "hdu-summer-2026");
  assert.equal(loaded.index.competitorById.size, 1);
});
