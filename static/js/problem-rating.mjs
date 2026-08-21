import { fetchJson, resolveDataUrl } from "./data.mjs?v=20260821-11";

const SCHEMA_VERSION = 1;
const validatedIndexes = new WeakSet();
const validatedSeries = new WeakSet();
const problemIndexCollator = new Intl.Collator("en", {
  numeric: true,
  sensitivity: "base",
});

function fail(path, message) {
  throw new TypeError(`${path}: ${message}`);
}

function object(value, path) {
  if (!value || typeof value !== "object" || Array.isArray(value)) fail(path, "expected object");
}

function string(value, path) {
  if (typeof value !== "string" || !value) fail(path, "expected non-empty string");
}

function text(value, path) {
  if (typeof value !== "string") fail(path, "expected string");
}

function integer(value, path, minimum = 0) {
  if (!Number.isSafeInteger(value) || value < minimum) fail(path, `expected integer >= ${minimum}`);
}

function array(value, path) {
  if (!Array.isArray(value)) fail(path, "expected array");
}

export function validateProblemRatingIndex(document) {
  object(document, "problemRatingIndex");
  if (validatedIndexes.has(document)) return document;
  integer(document.schemaVersion, "problemRatingIndex.schemaVersion", 1);
  if (document.schemaVersion !== SCHEMA_VERSION) {
    fail("problemRatingIndex.schemaVersion", `unsupported version ${document.schemaVersion}`);
  }
  array(document.series, "problemRatingIndex.series");
  if (!document.series.length) fail("problemRatingIndex.series", "expected at least one series");
  const ids = new Set();
  for (const [index, entry] of document.series.entries()) {
    const path = `problemRatingIndex.series[${index}]`;
    object(entry, path);
    string(entry.id, `${path}.id`);
    string(entry.title, `${path}.title`);
    string(entry.path, `${path}.path`);
    if (ids.has(entry.id)) fail(`${path}.id`, "duplicate series id");
    ids.add(entry.id);
  }
  validatedIndexes.add(document);
  return document;
}

export function validateProblemRatingSeries(document) {
  object(document, "problemRatingSeries");
  if (validatedSeries.has(document)) return document;
  integer(document.schemaVersion, "problemRatingSeries.schemaVersion", 1);
  if (document.schemaVersion !== SCHEMA_VERSION) {
    fail("problemRatingSeries.schemaVersion", `unsupported version ${document.schemaVersion}`);
  }
  string(document.seriesId, "problemRatingSeries.seriesId");
  string(document.title, "problemRatingSeries.title");
  string(document.modelId, "problemRatingSeries.modelId");
  array(document.contests, "problemRatingSeries.contests");
  if (!document.contests.length) fail("problemRatingSeries.contests", "expected at least one contest");

  const contestIds = new Set();
  for (const [contestIndex, contest] of document.contests.entries()) {
    const path = `problemRatingSeries.contests[${contestIndex}]`;
    object(contest, path);
    string(contest.id, `${path}.id`);
    string(contest.title, `${path}.title`);
    if (contest.shortTitle !== undefined) string(contest.shortTitle, `${path}.shortTitle`);
    string(contest.startAt, `${path}.startAt`);
    if (Number.isNaN(Date.parse(contest.startAt))) fail(`${path}.startAt`, "expected ISO date-time");
    if (contestIds.has(contest.id)) fail(`${path}.id`, "duplicate contest id");
    contestIds.add(contest.id);
    array(contest.problems, `${path}.problems`);
    if (!contest.problems.length) fail(`${path}.problems`, "expected at least one problem");
    const problemIndexes = new Set();
    for (const [problemIndex, problem] of contest.problems.entries()) {
      const problemPath = `${path}.problems[${problemIndex}]`;
      object(problem, problemPath);
      string(problem.index, `${problemPath}.index`);
      text(problem.name, `${problemPath}.name`);
      integer(problem.rating, `${problemPath}.rating`);
      integer(problem.solvedCount, `${problemPath}.solvedCount`);
      integer(problem.participantCount, `${problemPath}.participantCount`);
      integer(problem.timeSampleCount, `${problemPath}.timeSampleCount`);
      if (problem.solvedCount > problem.participantCount) {
        fail(`${problemPath}.solvedCount`, "exceeds participantCount");
      }
      if (problem.timeSampleCount > problem.solvedCount) {
        fail(`${problemPath}.timeSampleCount`, "exceeds solvedCount");
      }
      if (problemIndexes.has(problem.index)) fail(`${problemPath}.index`, "duplicate problem index");
      problemIndexes.add(problem.index);
    }
  }
  validatedSeries.add(document);
  return document;
}

export function compareProblemIndexes(left, right) {
  return problemIndexCollator.compare(left, right);
}

export function flattenProblemRatings(document, selectedContestIds = null) {
  validateProblemRatingSeries(document);
  const selected = selectedContestIds === null ? null : new Set(selectedContestIds);
  return document.contests.flatMap((contest, contestIndex) => {
    if (selected && !selected.has(contest.id)) return [];
    return contest.problems.map((problem, problemOrder) => ({
      contest,
      contestIndex,
      problem,
      problemOrder,
    }));
  });
}

export function problemSeriesHasNames(document) {
  return document.contests.some((contest) => contest.problems.some((problem) => problem.name));
}

function contestProblemComparison(left, right) {
  return left.contestIndex - right.contestIndex
    || compareProblemIndexes(left.problem.index, right.problem.index)
    || left.problemOrder - right.problemOrder;
}

export function sortProblemRows(rows, sort = "contest", order = "asc") {
  if (!new Set(["contest", "rating"]).has(sort)) throw new TypeError(`unknown sort: ${sort}`);
  if (!new Set(["asc", "desc"]).has(order)) throw new TypeError(`unknown order: ${order}`);
  const direction = order === "asc" ? 1 : -1;
  return [...rows].sort((left, right) => {
    if (sort === "contest") return contestProblemComparison(left, right) * direction;
    const ratingComparison = (left.problem.rating - right.problem.rating) * direction;
    return ratingComparison || contestProblemComparison(left, right);
  });
}

export function buildDifficultyCurves(document, selectedContestIds = null) {
  validateProblemRatingSeries(document);
  const selected = selectedContestIds === null ? null : new Set(selectedContestIds);
  return document.contests.flatMap((contest, contestIndex) => {
    if (selected && !selected.has(contest.id)) return [];
    const points = contest.problems
      .map((problem, problemOrder) => ({ problem, problemOrder }))
      .sort((left, right) => left.problem.rating - right.problem.rating
        || compareProblemIndexes(left.problem.index, right.problem.index)
        || left.problemOrder - right.problemOrder)
      .map((point, difficultyIndex) => ({ ...point, difficultyIndex }));
    return [{ contest, contestIndex, slotCount: points.length, points }];
  });
}

export function monotoneCubicPath(points) {
  if (!points.length) return "";
  if (points.length === 1) return `M ${points[0].x} ${points[0].y}`;
  const slopes = [];
  for (let index = 0; index < points.length - 1; index += 1) {
    const width = points[index + 1].x - points[index].x;
    if (width <= 0) throw new TypeError("curve x coordinates must be strictly increasing");
    slopes.push((points[index + 1].y - points[index].y) / width);
  }
  const tangents = [slopes[0]];
  for (let index = 1; index < points.length - 1; index += 1) {
    tangents.push(slopes[index - 1] * slopes[index] <= 0
      ? 0
      : (slopes[index - 1] + slopes[index]) / 2);
  }
  tangents.push(slopes.at(-1));
  for (let index = 0; index < slopes.length; index += 1) {
    if (slopes[index] === 0) {
      tangents[index] = 0;
      tangents[index + 1] = 0;
      continue;
    }
    const left = tangents[index] / slopes[index];
    const right = tangents[index + 1] / slopes[index];
    const magnitude = Math.hypot(left, right);
    if (magnitude > 3) {
      const scale = 3 / magnitude;
      tangents[index] = scale * left * slopes[index];
      tangents[index + 1] = scale * right * slopes[index];
    }
  }
  const commands = [`M ${points[0].x} ${points[0].y}`];
  for (let index = 0; index < points.length - 1; index += 1) {
    const left = points[index];
    const right = points[index + 1];
    const width = right.x - left.x;
    commands.push(
      `C ${left.x + width / 3} ${left.y + tangents[index] * width / 3}`
      + ` ${right.x - width / 3} ${right.y - tangents[index + 1] * width / 3}`
      + ` ${right.x} ${right.y}`,
    );
  }
  return commands.join(" ");
}

export function readProblemRatingQuery(url) {
  const params = new URL(url, "http://localhost/").searchParams;
  const selection = params.get("problemContests");
  return {
    view: params.get("view") === "problem-rating" ? "problem-rating" : "participants",
    selectedContestIds: selection === null
      ? null
      : selection === "none" ? [] : selection.split(",").filter(Boolean),
    sort: params.get("problemSort") === "rating" ? "rating" : "contest",
    order: params.get("problemOrder") === "desc" ? "desc" : "asc",
  };
}

export function writeProblemRatingQuery(url, query) {
  const next = new URL(url, "http://localhost/");
  if (query.view !== "problem-rating") {
    for (const key of ["view", "problemContests", "problemSort", "problemOrder"]) {
      next.searchParams.delete(key);
    }
    return next;
  }
  next.searchParams.set("view", "problem-rating");
  const allContestIds = query.allContestIds ?? [];
  const selectedContestIds = query.selectedContestIds ?? allContestIds;
  if (selectedContestIds.length === allContestIds.length
      && selectedContestIds.every((id) => allContestIds.includes(id))) {
    next.searchParams.delete("problemContests");
  } else if (!selectedContestIds.length) {
    next.searchParams.set("problemContests", "none");
  } else {
    next.searchParams.set("problemContests", selectedContestIds.join(","));
  }
  if (query.sort === "rating") next.searchParams.set("problemSort", "rating");
  else next.searchParams.delete("problemSort");
  if (query.order === "desc") next.searchParams.set("problemOrder", "desc");
  else next.searchParams.delete("problemOrder");
  return next;
}

export function createProblemRatingStore(indexUrl, fetchImpl = globalThis.fetch) {
  const indexPromise = fetchJson(indexUrl, fetchImpl).then(validateProblemRatingIndex);
  return {
    getIndex: () => indexPromise,
    async getSeries(id) {
      const index = await indexPromise;
      const entry = index.series.find((item) => item.id === id);
      if (!entry) throw new Error(`Unknown problem rating series: ${id}`);
      const series = validateProblemRatingSeries(
        await fetchJson(resolveDataUrl(entry.path, indexUrl), fetchImpl),
      );
      if (series.seriesId !== entry.id) {
        throw new TypeError(`problemRatingSeries.seriesId: expected ${entry.id}, received ${series.seriesId}`);
      }
      return { entry, series };
    },
  };
}
