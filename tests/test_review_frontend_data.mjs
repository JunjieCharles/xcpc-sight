import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { buildReviewAnalysis, spearmanRho, validateReview, createReviewStore,
  selectReviewRows, sortReviewRows, readReviewQuery, writeReviewQuery } from "../static/js/review.mjs";
import { buildPreviewPower, validatePreview, createPreviewStore, readPreviewQuery, writePreviewQuery } from "../static/js/preview.mjs";
import { clearJsonCache, validateIndex } from "../static/js/data.mjs";

const read = async path => JSON.parse(await readFile(new URL(path, import.meta.url), "utf8"));
const preview = validatePreview(await read("./fixtures/review/preview.json"));
const review = validateReview(await read("./fixtures/review/results.json"), [preview]);
const contest = review.contests[0];
const byId = analysis => Object.fromEntries(analysis.rows.map(t => [t.id, t]));

test("two filters preserve original power order and compress both ranks with ties", () => {
  const analysis = buildReviewAnalysis(preview, contest);
  const rows = byId(analysis);
  assert.deepEqual(Object.keys(rows), ["a", "c", "d"]);
  assert.equal(analysis.activeCount, 6);
  assert.equal(analysis.coverage, .5);
  assert.equal(rows.c.originalPowerRank, 3);
  assert.equal(rows.c.originalPreviewRank, 3);
  assert.equal(rows.c.originalActualRank, 5);
  assert.equal(rows.a.originalActualRank, 2);
  assert.equal(rows.d.originalActualRank, 2);
  assert.equal(rows.c.previewRank, 2);
  assert.deepEqual(analysis.rows.map(t => t.actualRank), [1, 3, 1]);
  assert.equal(rows.d.change, 2);
  assert.equal(rows.d.growth, Math.log10(3));
  assert.equal(rows.c.change, -1);
  assert.equal(rows.c.growth, Math.log10(2 / 3));
});

test("CPC Finder and medals keep zero records, exclude null and absences", () => {
  for (const metric of ["cpcfinder", "medals"]) {
    const rows = byId(buildReviewAnalysis(preview, contest, metric));
    assert.deepEqual(Object.keys(rows), ["a", "c", "d", "e", "f"]);
    assert.equal(rows.e.previewRank, 4);
    assert.equal(rows.f.previewRank, 4);
    assert.equal(rows.e.originalPreviewRank, 5);
    assert.equal(rows.f.originalPreviewRank, 5);
    assert.equal(rows.e.originalActualRank, 6);
    assert.equal(rows.e.actualRank, 5); // zero solves but has WA submissions
  }
  assert.deepEqual(Object.keys(byId(buildReviewAnalysis(preview, contest, "xcpcrating"))), ["a", "c", "d"]);
  for (const metric of ["xcpcrating", "xcpcElo", "previousSeason"]) {
    const row = byId(buildReviewAnalysis(preview, contest, metric)).c;
    assert.equal(row.originalPreviewRank, 3);
    assert.equal(row.previewRank, 2);
    assert.equal(row.originalActualRank, 5);
    assert.equal(row.actualRank, 3);
  }
  assert.throws(() => buildReviewAnalysis(preview, contest, "unknown"), /Unknown/);
});

test("Spearman rho covers concordance, inversions, average ties and zero correlation", () => {
  assert.equal(spearmanRho([[1, 1], [2, 2], [3, 3]]).value, 1);
  assert.equal(spearmanRho([[1, 3], [2, 2], [3, 1]]).value, -1);
  assert.equal(spearmanRho([[1, 1], [2, 3], [3, 2], [4, 4]]).value, 0.8);
  assert.ok(Math.abs(spearmanRho([[1, 1], [1, 2], [3, 3]]).value - Math.sqrt(3) / 2) < 1e-12);
  assert.ok(Math.abs(spearmanRho([[1, 1], [2, 1], [3, 3]]).value - Math.sqrt(3) / 2) < 1e-12);
  assert.equal(spearmanRho([[1, 1], [1, 1], [3, 3]]).value, 1);
  assert.equal(spearmanRho([[1, 2], [2, 4], [3, 1], [4, 3]]).value, 0);
  for (const pairs of [[], [[1, 1]], [[1, 1], [1, 1]], [[1, 1], [1, 2]]]) {
    assert.equal(spearmanRho(pairs).value, null);
    assert.ok(spearmanRho(pairs).reason);
  }
  // Re-ranking makes the result independent of competition-rank gaps and score scale.
  assert.ok(Math.abs(spearmanRho([[10, 1], [10, 2], [900, 3]]).value - Math.sqrt(3) / 2) < 1e-12);
  for (const pairs of [null, [[NaN, 1]], [[1, Infinity]], [[1]], [["1", 2]]]) {
    assert.throws(() => spearmanRho(pairs), /finite numeric pairs/);
  }
});

test("search and sorting only change display; cached analysis is reused", () => {
  const analysis = buildReviewAnalysis(preview, contest);
  assert.equal(buildReviewAnalysis(preview, contest), analysis);
  assert.notEqual(buildReviewAnalysis(preview, contest, "medals"), analysis);
  const rows = selectReviewRows(analysis, { query: "Member c", schools: ["University"] });
  assert.equal(rows.length, 1);
  assert.equal(rows[0].previewRank, 2);
  assert.equal(rows[0].actualRank, 3);
  assert.equal(analysis.rows.length, 3);
  assert.deepEqual(sortReviewRows(analysis).map(t => t.id), ["a", "d", "c"]);
  assert.deepEqual(sortReviewRows(analysis, "change", "desc").map(t => t.id), ["d", "a", "c"]);
  assert.deepEqual(sortReviewRows(analysis, "metric", "desc").map(t => t.id), ["a", "c", "d"]);
  assert.deepEqual(sortReviewRows(analysis, "name", "desc").map(t => t.id), ["d", "c", "a"]);
  const close = { rows: [
    { id: "a", growth: .10001, school: "A", sourceIndex: 0 },
    { id: "b", growth: .10002, school: "B", sourceIndex: 1 },
  ] };
  assert.deepEqual(sortReviewRows(close, "growth", "desc").map(t => t.id), ["b", "a"]);
});

test("empty and one-team cohorts remain usable without a coefficient", () => {
  const empty = structuredClone(contest);
  empty.teams.forEach(t => { t.hasActivity = false; t.actualRank = null; });
  let analysis = buildReviewAnalysis(preview, empty);
  assert.equal(analysis.rows.length, 0);
  assert.equal(analysis.coverage, null);
  assert.equal(analysis.agreement.value, null);
  const single = structuredClone(empty);
  single.teams[0].hasActivity = true;
  single.teams[0].actualRank = 1;
  analysis = buildReviewAnalysis(preview, single);
  assert.equal(analysis.rows[0].growth, 0);
  assert.equal(analysis.agreement.value, null);
});

test("review validation rejects missing joins, duplicate results and invalid activity ranks", () => {
  for (const mutate of [
    d => { d.schemaVersion = 2; }, d => { d.seriesId = "other"; },
    d => { d.contests[0].previewId = "unknown"; },
    d => { d.contests[0].teams.pop(); },
    d => { d.contests[0].teams[1].previewTeamId = "a"; },
    d => { d.contests[0].teams[1].resultTeamId = "result-a"; },
    d => { d.contests[0].teams[0].actualRank = 0; },
    d => { d.contests[0].teams[1].actualRank = 1; },
    d => { d.contests.push(d.contests[0]); },
  ]) {
    const invalid = structuredClone(review); mutate(invalid);
    assert.throws(() => validateReview(invalid, [preview]), /review\./);
  }
});

test("review URL roundtrip, invalid sort fallback and unrelated state preservation", () => {
  const next = writeReviewQuery("https://example.test/site/?q=team&school=A&unrelated=yes", {
    view: "review", contest: "actual-one", metric: "medals", sort: "growth", order: "desc",
  });
  assert.equal(next.searchParams.get("view"), "review");
  assert.deepEqual(readReviewQuery(next), {
    reviewContest: "actual-one", reviewMetric: "medals", reviewSort: "growth", reviewOrder: "desc",
  });
  assert.equal(next.searchParams.get("q"), "team");
  assert.equal(next.searchParams.get("unrelated"), "yes");
  assert.equal(readReviewQuery("https://example.test/?reviewSort=bad").reviewSort, "actualRank");
  const left = writeReviewQuery(next, { view: "participants" });
  assert.equal(left.searchParams.has("reviewMetric"), false);
  assert.equal(left.searchParams.has("view"), false);
  const p = writePreviewQuery(next, { view: "preview", contest: "preview-two" });
  assert.equal(readPreviewQuery(p).previewContest, "preview-two");
});

test("legacy and multiple previews resolve relative URLs and validate explicit IDs", async () => {
  clearJsonCache();
  const second = { ...structuredClone(preview), id: "preview-two" };
  const indexUrl = "https://multi.example.test/sub/data/index.json";
  const entry = { id: preview.seriesId, title: preview.seriesTitle, previewPath: "previews/one.json",
    previews: [{ id: preview.id, path: "previews/one.json" }, { id: second.id, path: "previews/two.json" }],
    reviewPath: "reviews/series.json" };
  const seen = [];
  const fetchImpl = async url => {
    seen.push(url);
    return { ok: true, json: async () => url.includes("/reviews/") ? review : url.endsWith("two.json") ? second : preview };
  };
  validateIndex({ schemaVersion: 2, defaultSeriesId: entry.id, series: [entry] });
  const store = createPreviewStore(indexUrl, fetchImpl);
  const loaded = await store.getPreviews(entry);
  assert.deepEqual(loaded.map(p => p.id), [preview.id, second.id]);
  assert.equal(await store.getSeries({ ...entry, previews: undefined }), preview);
  assert.equal(await createReviewStore(indexUrl, fetchImpl).getSeries(entry, loaded), review);
  assert.ok(seen.every(url => url.startsWith("https://multi.example.test/sub/data/")));
  await assert.rejects(store.getPreviews({ ...entry, previews: [{ id: "wrong", path: "previews/one.json" }] }), /preview.id/);
});

test("failed review fetch can be retried without affecting preview availability", async () => {
  clearJsonCache();
  let attempts = 0;
  const store = createReviewStore("https://retry.example.test/data/index.json", async () => ({
    ok: ++attempts > 1, status: 503, json: async () => review,
  }));
  const entry = { reviewPath: "review.json" };
  await assert.rejects(store.getSeries(entry, [preview]), /503/);
  assert.equal(await store.getSeries(entry, [preview]), review);
  assert.equal(await store.getSeries({}, [preview]), null);
});

test("published first preliminary joins all teams and retains 1972 nonzero original power teams", async () => {
  const p = validatePreview(await read("../static/data/previews/2026-2027.json"));
  const second = validatePreview(await read("../static/data/previews/icpc-2026-preliminary-2.json"));
  const r = validateReview(await read("../static/data/reviews/2026-2027.json"), [p, second]);
  assert.equal(r.contests[0].teams.length, 2535);
  assert.equal(r.contests[0].teams.filter(t => t.hasActivity).length, 2496);
  const power = buildPreviewPower(p.teams);
  assert.equal([...power.values()].filter(t => t.vector.some(v => v !== 0)).length, 1972);
  const analysis = buildReviewAnalysis(p, r.contests[0]);
  assert.equal(analysis.rows.length, 1950);
  assert.equal(analysis.agreement.value.toFixed(3), "0.736");
  // Reference values calculated with scipy.stats.spearmanr on these same filtered teams.
  const expected = {
    power: 0.7358560837348063, xcpcrating: 0.7445437433129665,
    xcpcElo: 0.7310809988653579, previousSeason: 0.6704024441505873,
    cpcfinder: 0.6425002771082232, medals: 0.6615396075355272,
  };
  for (const [metric, value] of Object.entries(expected)) {
    assert.ok(Math.abs(buildReviewAnalysis(p, r.contests[0], metric).agreement.value - value) < 1e-12);
  }
  assert.ok(Number.isFinite(analysis.agreement.value));
  const sorted = sortReviewRows(analysis, "previewRank");
  for (let i = 1; i < sorted.length; i++) assert.ok(sorted[i].originalPowerRank >= sorted[i - 1].originalPowerRank);
});

test("published second preliminary joins all teams and compares all seven pre-contest metrics", async () => {
  const first = validatePreview(await read("../static/data/previews/2026-2027.json"));
  const p = validatePreview(await read("../static/data/previews/icpc-2026-preliminary-2.json"));
  const r = validateReview(await read("../static/data/reviews/2026-2027.json"), [first, p]);
  assert.deepEqual(r.contests.map(c => c.id), ["icpc2026preliminary-1", "icpc2026preliminary-2"]);
  const c = r.contests[1];
  assert.equal(c.previewId, p.id);
  assert.equal(c.startAt, "2026-09-12T13:00:00+08:00");
  assert.equal(c.source.fileId, "92205039610843136");
  assert.equal(c.source.sha256, "ab6a796e4ca65f1ba6dc8c9c87174a49aab7439cee6aacee17d3ce1285a9ceea");
  assert.equal(c.teams.length, 2636);
  assert.equal(c.teams.filter(t => t.hasActivity).length, 2535);
  assert.equal(c.teams.filter(t => !t.hasActivity && t.actualRank === null).length, 101);
  // Independently verified with scipy.stats.spearmanr on each filtered cohort.
  const expected = {
    power: [2403, 0.7976612856593243], xcpcrating: [2400, 0.8205084976990384],
    xcpcElo: [2390, 0.8137796644791935], previousSeason: [1312, 0.6667139073240879],
    currentSeason: [2224, 0.8102420013496722], cpcfinder: [996, 0.6510521285590931],
    medals: [996, 0.662419864427567],
  };
  assert.deepEqual(["power", ...p.metricSources.map(m => m.id), "medals"], Object.keys(expected));
  for (const [metric, [count, rho]] of Object.entries(expected)) {
    const a = buildReviewAnalysis(p, c, metric);
    assert.equal(a.rows.length, count);
    assert.equal(a.coverage, count / 2535);
    assert.ok(Math.abs(a.agreement.value - rho) < 1e-12);
  }
});

test("all six metric comparisons remain available and contest changes use independent caches", () => {
  const metrics = ["power", ...preview.metricSources.map(m => m.id), "medals"];
  const summaries = metrics.map(metric => buildReviewAnalysis(preview, contest, metric));
  assert.equal(summaries.length, 6);
  assert.deepEqual(summaries.map(a => a.rows.length), [3, 3, 3, 3, 5, 5]);
  const other = structuredClone(contest);
  other.id = "actual-two";
  other.teams.forEach(t => { if (t.hasActivity) t.actualRank = 10 - t.actualRank; });
  for (let i = 0; i < metrics.length; i++) {
    const next = buildReviewAnalysis(preview, other, metrics[i]);
    assert.notEqual(next, summaries[i]);
    assert.ok(Math.abs(next.agreement.value + summaries[i].agreement.value) < 1e-12);
    assert.equal(buildReviewAnalysis(preview, contest, metrics[i]), summaries[i]);
  }
});
