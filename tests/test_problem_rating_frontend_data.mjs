import assert from "node:assert/strict";
import test from "node:test";

import {
  buildDifficultyCurves,
  createProblemRatingStore,
  flattenProblemRatings,
  monotoneCubicPath,
  problemSeriesHasNames,
  readProblemRatingQuery,
  sortProblemRows,
  validateProblemRatingIndex,
  validateProblemRatingSeries,
  writeProblemRatingQuery,
} from "../static/js/problem-rating.mjs";

function fixture() {
  return {
    schemaVersion: 1,
    seriesId: "nowcoder-summer-2026",
    title: "Nowcoder",
    modelId: "gaussian-prev1-3-shallow-gbr-no-order",
    contests: [
      {
        id: "nowcoder:1",
        title: "Contest 1",
        shortTitle: "第一场",
        startAt: "2026-07-01T12:00:00+08:00",
        problems: [
          { index: "A", name: "A", rating: 1800, solvedCount: 20, participantCount: 100, timeSampleCount: 10 },
          { index: "B", name: "B", rating: 1200, solvedCount: 80, participantCount: 100, timeSampleCount: 60 },
        ],
      },
      {
        id: "nowcoder:2",
        title: "Contest 2",
        startAt: "2026-07-03T12:00:00+08:00",
        problems: [
          { index: "A2", name: "A2", rating: 1800, solvedCount: 10, participantCount: 90, timeSampleCount: 5 },
          { index: "A10", name: "A10", rating: 2400, solvedCount: 3, participantCount: 90, timeSampleCount: 2 },
          { index: "C", name: "C", rating: 1400, solvedCount: 60, participantCount: 90, timeSampleCount: 30 },
        ],
      },
    ],
  };
}

test("validates problem-rating documents and count invariants", () => {
  const document = fixture();
  document.contests[0].problems[0].name = "";
  assert.equal(validateProblemRatingSeries(document), document);
  assert.equal(validateProblemRatingSeries(document), document);
  const invalid = fixture();
  invalid.contests[0].problems[0].timeSampleCount = 21;
  assert.throws(() => validateProblemRatingSeries(invalid), /exceeds solvedCount/);
  const invalidShortTitle = fixture();
  invalidShortTitle.contests[0].shortTitle = "";
  assert.throws(() => validateProblemRatingSeries(invalidShortTitle), /shortTitle/);

  const index = {
    schemaVersion: 1,
    series: [{ id: document.seriesId, title: document.title, path: "series/nowcoder.json" }],
  };
  assert.equal(validateProblemRatingIndex(index), index);
});

test("reports whether a problem-rating series contains any problem names", () => {
  assert.equal(problemSeriesHasNames(fixture()), true);
  const unnamed = structuredClone(fixture());
  for (const contest of unnamed.contests) {
    for (const problem of contest.problems) problem.name = "";
  }
  assert.equal(problemSeriesHasNames(unnamed), false);
});

test("filters contests and supports both deterministic sort modes", () => {
  const rows = flattenProblemRatings(fixture(), ["nowcoder:2"]);
  assert.equal(rows.length, 3);
  assert.deepEqual(
    sortProblemRows(rows, "contest", "asc").map(({ problem }) => problem.index),
    ["A2", "A10", "C"],
  );
  assert.deepEqual(
    sortProblemRows(rows, "contest", "desc").map(({ problem }) => problem.index),
    ["C", "A10", "A2"],
  );
  const allRows = flattenProblemRatings(fixture());
  assert.deepEqual(
    sortProblemRows(allRows, "rating", "asc").map(({ problem }) => problem.rating),
    [1200, 1400, 1800, 1800, 2400],
  );
  assert.deepEqual(
    sortProblemRows(allRows, "rating", "desc").map(({ problem }) => problem.rating),
    [2400, 1800, 1800, 1400, 1200],
  );
});

test("builds easy-to-hard curves without normalizing contest lengths", () => {
  const curves = buildDifficultyCurves(fixture());
  assert.deepEqual(curves.map(({ slotCount }) => slotCount), [2, 3]);
  assert.deepEqual(
    curves[0].points.map(({ problem }) => problem.index),
    ["B", "A"],
  );
  assert.deepEqual(
    curves[1].points.map(({ problem }) => problem.rating),
    [1400, 1800, 2400],
  );

  const path = monotoneCubicPath([
    { x: 10, y: 100 },
    { x: 58, y: 80 },
    { x: 106, y: 20 },
  ]);
  assert.match(path, /^M 10 100 C /);
  assert.match(path, / 106 20$/);
  assert.doesNotMatch(path, /NaN|Infinity/);
});

test("round trips problem-rating view, selection and sorting through URL state", () => {
  const next = writeProblemRatingQuery("https://example.test/?series=nowcoder-summer-2026", {
    view: "problem-rating",
    allContestIds: ["nowcoder:1", "nowcoder:2"],
    selectedContestIds: ["nowcoder:2"],
    sort: "rating",
    order: "desc",
  });
  assert.deepEqual(readProblemRatingQuery(next), {
    view: "problem-rating",
    selectedContestIds: ["nowcoder:2"],
    sort: "rating",
    order: "desc",
  });
  const none = writeProblemRatingQuery(next, {
    view: "problem-rating",
    allContestIds: ["nowcoder:1", "nowcoder:2"],
    selectedContestIds: [],
    sort: "contest",
    order: "asc",
  });
  assert.deepEqual(readProblemRatingQuery(none).selectedContestIds, []);
  const participants = writeProblemRatingQuery(none, { view: "participants" });
  assert.equal(participants.searchParams.has("view"), false);
  assert.equal(participants.searchParams.has("problemContests"), false);
});

test("loads only a requested problem-rating series from its independent index", async () => {
  const document = fixture();
  const index = {
    schemaVersion: 1,
    series: [{ id: document.seriesId, title: document.title, path: "series/nowcoder.json" }],
  };
  const responses = new Map([
    ["https://example.test/site/data/problem-rating/index.json", index],
    ["https://example.test/site/data/problem-rating/series/nowcoder.json", document],
  ]);
  const store = createProblemRatingStore(
    "https://example.test/site/data/problem-rating/index.json",
    async (url) => ({
      ok: responses.has(url),
      status: responses.has(url) ? 200 : 404,
      json: async () => responses.get(url),
    }),
  );
  assert.equal((await store.getIndex()).series.length, 1);
  assert.equal((await store.getSeries(document.seriesId)).series, document);
  await assert.rejects(store.getSeries("hdu-summer-2026"), /Unknown problem rating series/);
});
