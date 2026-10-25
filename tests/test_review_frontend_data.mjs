import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { buildReviewAnalysis, reviewMetrics, sortReviewContests, medalPredictionAccuracy, spearmanRho, validateReview, createReviewStore,
  selectReviewRows, sortReviewRows, readReviewQuery, writeReviewQuery } from "../static/js/review.mjs";
import { buildPreviewPower, previewPowerMetricIds, validatePreview, createPreviewStore, readPreviewQuery, writePreviewQuery } from "../static/js/preview.mjs";
import { clearJsonCache, validateIndex } from "../static/js/data.mjs";

const read = async path => JSON.parse(await readFile(new URL(path, import.meta.url), "utf8"));
const preview = validatePreview(await read("./fixtures/review/preview.json"));
const review = validateReview(await read("./fixtures/review/results.json"), [preview]);
const contest = review.contests[0];
const byId = analysis => Object.fromEntries(analysis.rows.map(t => [t.id, t]));
const regionalPreviews = await Promise.all(["icpc-2026-xian", "ccpc-2026-changchun", "icpc-2026-chengdu"]
  .map(async id => validatePreview(await read(`../static/data/previews/${id}.json`))));

test("review menu uses Beijing dates and ICPC precedes later-starting CCPC on the same date", () => {
  const icpc = { id: "icpc2026xi_an", startAt: "2026-10-18T01:00:00Z" };
  const ccpc = { id: "ccpc2026changchun", startAt: "2026-10-18T13:00:00+08:00" };
  const later = { id: "ccpc2026later", startAt: "2026-10-18T16:00:00Z" };
  const input = [later, ccpc, icpc];
  assert.deepEqual(sortReviewContests(input), [icpc, ccpc, later]);
  assert.deepEqual(input, [later, ccpc, icpc]);
});

test("medal precision counts exact bands, ties, no predictions and missing metric cohorts", () => {
  const score = medalPredictionAccuracy([
    { previewRank: 1, actualMedal: "silver" },
    { previewRank: 2, actualMedal: "gold" },
    { previewRank: 3, actualMedal: "bronze" },
    { previewRank: 4, actualMedal: null },
  ]);
  assert.deepEqual(score.gold, { hits: 0, predicted: 1, value: 0 });
  assert.deepEqual(score.silver, { hits: 0, predicted: 1, value: 0 });
  assert.deepEqual(score.bronze, { hits: 1, predicted: 1, value: 1 });
  const tied = medalPredictionAccuracy([
    { previewRank: 1, actualMedal: "gold" }, { previewRank: 1, actualMedal: "silver" },
  ]);
  assert.deepEqual(tied.gold, { hits: 1, predicted: 2, value: .5 });
  assert.deepEqual(tied.silver, { hits: 0, predicted: 0, value: null });
  assert.equal(medalPredictionAccuracy([]).bronze.value, null);
  const r = structuredClone(review);
  r.contests[0].hasMedals = true;
  r.contests[0].teams.forEach(t => { t.actualMedal = t.hasActivity ? "bronze" : null; });
  Object.assign(r.contests[0].teams[0], { resultStatus: "unofficial", hasActivity: null, actualRank: null, actualMedal: null });
  validateReview(r, [preview]);
  const analysis = buildReviewAnalysis(preview, r.contests[0]);
  assert.equal(analysis.activeCount, 5);
  assert.equal(analysis.medalAccuracy.bronze.predicted, analysis.rows.length);
  assert.equal(analysis.medalAccuracy.bronze.value, 1);
  assert.equal(buildReviewAnalysis(preview, contest).medalAccuracy, null);
  const invalid = structuredClone(r);
  invalid.contests[0].teams[0].actualMedal = "gold";
  assert.throws(() => validateReview(invalid, [preview]), /inactive/);
  invalid.contests[0].teams[0].actualMedal = "bad";
  assert.throws(() => validateReview(invalid, [preview]), /actualMedal/);
});

test("excluded preview teams are absent from review and all metric cohorts", () => {
  const p = structuredClone(preview);
  p.teams[0].excluded = true;
  const r = structuredClone(review);
  r.contests[0].teams = r.contests[0].teams.filter(t => t.previewTeamId !== p.teams[0].id);
  validateReview(r, [p]);
  for (const metric of ["power", ...p.metricSources.map(s => s.id), "medals"]) {
    const a = buildReviewAnalysis(p, r.contests[0], metric);
    assert.equal(a.activeCount, 5);
    assert.ok(a.rows.every(t => !t.excluded));
    assert.equal(a.coverage, a.rows.length / 5);
  }
  const invalid = structuredClone(r);
  invalid.contests[0].teams.push(contest.teams[0]);
  assert.throws(() => validateReview(invalid, [p]), /unknown or duplicate preview team/);
});

test("explicit removed results preserve roster coverage but leave all analysis cohorts", () => {
  const revised = structuredClone(review);
  const removed = revised.contests[0].teams[0];
  Object.assign(removed, { resultStatus: "removed", hasActivity: null, actualRank: null });
  validateReview(revised, [preview]);
  for (const metric of ["power", ...preview.metricSources.map(s => s.id), "medals"]) {
    const a = buildReviewAnalysis(preview, revised.contests[0], metric);
    assert.equal(a.activeCount, 5);
    assert.ok(a.rows.every(t => t.id !== removed.previewTeamId));
    assert.equal(a.coverage, a.rows.length / 5);
  }
  for (const change of [
    { resultStatus: "unknown" }, { resultStatus: null },
    { hasActivity: false }, { hasActivity: true }, { actualRank: 1 },
  ]) {
    const invalid = structuredClone(revised);
    Object.assign(invalid.contests[0].teams[0], change);
    assert.throws(() => validateReview(invalid, [preview]), /resultStatus|removed results/);
  }
  const missing = structuredClone(revised);
  missing.contests[0].teams.shift();
  assert.throws(() => validateReview(missing, [preview]), /missing preview teams/);
});

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
  const ccpc = validatePreview(await read("../static/data/previews/ccpc-2026-preliminary.json"));
  const r = validateReview(await read("../static/data/reviews/2026-2027.json"), [p, second, ccpc, ...regionalPreviews]);
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
  const ccpc = validatePreview(await read("../static/data/previews/ccpc-2026-preliminary.json"));
  const r = validateReview(await read("../static/data/reviews/2026-2027.json"), [first, p, ccpc, ...regionalPreviews]);
  assert.deepEqual(r.contests.map(c => c.id), ["icpc2026preliminary-1", "icpc2026preliminary-2", "ccpc2026preliminary", "icpc2026xi_an", "ccpc2026changchun", "icpc2026chengdu"]);
  const c = r.contests[1];
  assert.equal(c.previewId, p.id);
  assert.equal(c.startAt, "2026-09-12T13:00:00+08:00");
  assert.equal(c.source.fileId, "94656957834690560");
  assert.equal(c.source.sha256, "a501dca75c4814277ed6a7b897db379b5ee4b3b1b560be4bc0c2cc8c84fb3fc9");
  assert.equal(c.teams.length, 2636);
  assert.equal(c.teams.filter(t => t.hasActivity).length, 2521);
  assert.equal(c.teams.filter(t => t.hasActivity === false && t.actualRank === null).length, 101);
  const removed = c.teams.filter(t => t.resultStatus === "removed");
  assert.equal(removed.length, 14);
  assert.ok(removed.every(t => t.hasActivity === null && t.actualRank === null));
  assert.deepEqual(removed.map(t => t.resultTeamId).sort(),
    ["1310", "1311", "1307", "1265", "323", "1305", "1301", "1303", "1306", "1266", "1308", "1264", "1302", "322"].sort());
  // Independently verified with scipy.stats.spearmanr on each filtered cohort.
  const expected = {
    power: [2389, 0.7979673905820589], xcpcrating: [2386, 0.820007206075806],
    xcpcElo: [2376, 0.8137117635270318], previousSeason: [1307, 0.6663258603271373],
    currentSeason: [2212, 0.8094589659447637], cpcfinder: [991, 0.6511412263831494],
    medals: [991, 0.6627187012991854],
  };
  assert.deepEqual(["power", ...p.metricSources.map(m => m.id), "medals"], Object.keys(expected));
  for (const [metric, [count, rho]] of Object.entries(expected)) {
    const a = buildReviewAnalysis(p, c, metric);
    assert.equal(a.rows.length, count);
    assert.equal(a.coverage, count / 2521);
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


test("published CCPC review covers only official teams and seven verified metrics", async () => {
  const ps = await Promise.all(["2026-2027", "icpc-2026-preliminary-2", "ccpc-2026-preliminary"]
    .map(async id => validatePreview(await read(`../static/data/previews/${id}.json`))));
  const r = validateReview(await read("../static/data/reviews/2026-2027.json"), [...ps, ...regionalPreviews]);
  const p = ps[2], c = r.contests[2];
  assert.equal(c.id, "ccpc2026preliminary");
  assert.equal(c.previewId, p.id);
  assert.equal(c.startAt, "2026-09-19T13:00:00+08:00");
  assert.equal(c.source.fileId, "95451702349623296");
  assert.equal(c.source.sha256, "d579046c9b6bde35c9b0178fdcda574c8a2ca7f9d1a52b2110349dd2010594b1");
  assert.equal(c.teams.length, 2169);
  assert.equal(c.teams.filter(t => t.hasActivity).length, 2106);
  assert.equal(c.teams.filter(t => t.hasActivity === false && t.actualRank === null).length, 60);
  const removed = c.teams.filter(t => t.resultStatus === "removed");
  assert.deepEqual(removed.map(t => t.resultTeamId).sort(), ["6", "687", "769"]);
  assert.ok(removed.every(t => t.hasActivity === null && t.actualRank === null));
  const mapping = await read("../config/review-removed-results/ccpc2026preliminary.json");
  assert.deepEqual(Object.fromEntries(removed.map(t => [t.previewTeamId, t.resultTeamId])), mapping);
  assert.deepEqual(new Set(c.teams.map(t => t.previewTeamId)), new Set(p.teams.filter(t => !t.excluded).map(t => t.id)));
  // Independently checked with scipy.stats.spearmanr, including tied ranks.
  const expected = {
    power: [2044, 0.8251774661344153], xcpcrating: [2043, 0.8724886056691887],
    xcpcElo: [2040, 0.8904363612890709], previousSeason: [1127, 0.706498663761117],
    currentSeason: [1964, 0.8691749918667957], cpcfinder: [871, 0.6410781746824133],
    medals: [871, 0.6574826994852914],
  };
  for (const [metric, [count, rho]] of Object.entries(expected)) {
    const a = buildReviewAnalysis(p, c, metric);
    assert.equal(a.rows.length, count);
    assert.equal(a.activeCount, 2106);
    assert.equal(a.coverage, count / 2106);
    assert.ok(a.rows.every(t => !t.excluded));
    assert.ok(a.rows.every(t => !Object.hasOwn(mapping, t.id)));
    assert.ok(Math.abs(a.agreement.value - rho) < 1e-12);
  }
});

test("regional reviews preserve preview power and compare only its constituent metrics", async () => {
  const network = await Promise.all(["2026-2027", "icpc-2026-preliminary-2", "ccpc-2026-preliminary"]
    .map(async id => validatePreview(await read(`../static/data/previews/${id}.json`))));
  const doc = validateReview(await read("../static/data/reviews/2026-2027.json"), [...network, ...regionalPreviews]);
  // Coefficients independently checked using scipy.stats.spearmanr; counts by band intersection.
  const expected = await read("./fixtures/review/regional-metrics.json");
  for (const p of regionalPreviews) {
    const c = doc.contests.find(c => c.previewId === p.id);
    const original = structuredClone(p);
    const activeCount = c.id === "icpc2026chengdu" ? 319 : c.id === "icpc2026xi_an" ? 402 : 298;
    assert.equal(c.source.fileId, c.id === "icpc2026chengdu" ? "107769046547718144" : c.id === "icpc2026xi_an" ? "105318714861256704" : "105706787390464000");
    assert.equal(c.source.url, `https://rl.algoux.cn/ranklist/${c.id}`);
    const power = buildPreviewPower(p.teams, p.metricSources.map(m => m.id), previewPowerMetricIds(p));
    assert.deepEqual(reviewMetrics(p).map(m => m.id), Object.keys(expected[c.id]));
    assert.deepEqual(new Set(reviewMetrics(p).map(m => m.id)), new Set(["power", ...p.powerMetrics]));
    for (const omitted of ["cpcfinder", "medals"]) assert.throws(() => buildReviewAnalysis(p, c, omitted), /Unknown review metric/);
    for (const metric of reviewMetrics(p).map(m => m.id)) {
      const a = buildReviewAnalysis(p, c, metric);
      const [count, rho, medals] = expected[c.id][metric];
      assert.equal(a.rows.length, count);
      assert.equal(a.activeCount, activeCount);
      assert.ok(Math.abs(a.agreement.value - rho) < 1e-12);
      for (const row of a.rows) assert.equal(row.originalPowerRank, power.get(row.id).rank);
      for (const [i, key] of ["gold", "silver", "bronze"].entries()) {
        assert.deepEqual([a.medalAccuracy[key].hits, a.medalAccuracy[key].predicted], medals[i]);
        assert.equal(a.medalAccuracy[key].value, medals[i][1] ? medals[i][0] / medals[i][1] : null);
      }
      selectReviewRows(a, { query: "北京", sort: "metric", order: "desc" });
      assert.equal(buildReviewAnalysis(p, c, metric), a);
    }
    assert.deepEqual(p, original);
    if (c.id === "icpc2026xi_an") {
      assert.deepEqual(c.teams.filter(t => t.resultStatus === "unofficial").map(t => t.resultTeamId), ["Team366"]);
    } else if (c.id === "ccpc2026changchun") {
      assert.deepEqual(["gold", "silver", "bronze"].map(medal =>
        c.teams.filter(t => t.actualMedal === medal).length), [30, 60, 90]);
      for (const row of c.teams) {
        const rank = row.actualRank;
        assert.equal(row.actualMedal, rank == null ? null : rank <= 30 ? "gold"
          : rank <= 90 ? "silver" : rank <= 180 ? "bronze" : null);
      }
      assert.ok(c.teams.some(t => t.previewTeamId === "t_35484354206ca267e86a" && t.resultTeamId === "I1000" && t.hasActivity));
      assert.ok(!c.teams.some(t => t.resultTeamId === "I10"));
    }
  }
});


test("Chengdu history includes Changchun's corrected final bronze place", async () => {
  const preview = await read("../static/data/previews/icpc-2026-chengdu.json");
  const records = preview.teams.flatMap(t => t.currentSeasonHistory ?? [])
    .filter(h => h.contestId === "ccpc2026changchun" && h.teamId === "F28");
  assert.equal(records.length, 1);
  assert.equal(records[0].rank, 180);
  assert.equal(records[0].medal, "bronze");
});


test("Chengdu joins every official team and preserves fixed medal boundaries", async () => {
  const p = regionalPreviews.find(p => p.id === "icpc-2026-chengdu");
  const c = (await read("../static/data/reviews/2026-2027.json")).contests.at(-1);
  assert.equal(c.id, "icpc2026chengdu");
  assert.equal(c.startAt, "2026-10-25T09:10:00+08:00");
  assert.equal(c.source.sha256, "23f0b373820c561d0f219de014ed65ff0e6c6496e818d4d55f8673cb46aa6882");
  assert.equal(c.teams.length, 319);
  assert.equal(new Set(c.teams.map(t => t.resultTeamId)).size, 319);
  assert.deepEqual(new Set(c.teams.map(t => t.previewTeamId)), new Set(p.teams.filter(t => !t.excluded).map(t => t.id)));
  assert.deepEqual(["gold", "silver", "bronze"].map(m => c.teams.filter(t => t.actualMedal === m).length), [32, 64, 96]);
  for (const t of c.teams) {
    assert.equal(t.hasActivity, true);
    assert.equal(t.resultStatus, undefined);
    assert.equal(t.actualMedal, t.actualRank <= 32 ? "gold" : t.actualRank <= 96 ? "silver" : t.actualRank <= 192 ? "bronze" : null);
  }
  assert.throws(() => buildReviewAnalysis(p, c, "previousSeason"), /Unknown review metric/);
});
