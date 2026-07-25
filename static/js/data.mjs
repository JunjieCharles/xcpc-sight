const SCHEMA_VERSION = 1;
const jsonPromises = new Map();
const validatedIndexes = new WeakSet();
const validatedSeries = new WeakSet();
const indexedSeries = new WeakMap();

function fail(path, message) {
  throw new TypeError(`${path}: ${message}`);
}

function object(value, path) {
  if (!value || typeof value !== "object" || Array.isArray(value)) fail(path, "expected object");
  return value;
}

function string(value, path) {
  if (typeof value !== "string" || !value) fail(path, "expected non-empty string");
}

function text(value, path) {
  if (typeof value !== "string") fail(path, "expected string");
}

function integer(value, path, minimum = Number.MIN_SAFE_INTEGER) {
  if (!Number.isSafeInteger(value) || value < minimum) fail(path, `expected integer >= ${minimum}`);
}

function array(value, path) {
  if (!Array.isArray(value)) fail(path, "expected array");
}

export function resolveDataUrl(path, baseUrl) {
  string(path, "path");
  const base = new URL(baseUrl, globalThis.location?.href || "http://localhost/");
  return new URL(path, base).href;
}

export function fetchJson(url, fetchImpl = globalThis.fetch) {
  const absolute = new URL(url, globalThis.location?.href || "http://localhost/").href;
  if (!jsonPromises.has(absolute)) {
    jsonPromises.set(absolute, Promise.resolve(fetchImpl(absolute, { cache: "no-cache" })).then((response) => {
      if (!response.ok) throw new Error(`Unable to load ${absolute} (${response.status})`);
      return response.json();
    }).catch((error) => {
      jsonPromises.delete(absolute);
      throw error;
    }));
  }
  return jsonPromises.get(absolute);
}

export function clearJsonCache() {
  jsonPromises.clear();
}

export function validateIndex(document) {
  object(document, "index");
  if (validatedIndexes.has(document)) return document;
  integer(document.schemaVersion, "index.schemaVersion", 1);
  if (document.schemaVersion !== SCHEMA_VERSION) fail("index.schemaVersion", `unsupported version ${document.schemaVersion}`);
  string(document.defaultSeriesId, "index.defaultSeriesId");
  array(document.series, "index.series");
  if (!document.series.length) fail("index.series", "expected at least one series");
  const ids = new Set();
  for (const [i, item] of document.series.entries()) {
    object(item, `index.series[${i}]`);
    string(item.id, `index.series[${i}].id`);
    string(item.title, `index.series[${i}].title`);
    string(item.path, `index.series[${i}].path`);
    if (ids.has(item.id)) fail(`index.series[${i}].id`, "duplicate series id");
    ids.add(item.id);
  }
  if (!ids.has(document.defaultSeriesId)) fail("index.defaultSeriesId", "does not reference a series");
  validatedIndexes.add(document);
  return document;
}

export function validateSeries(document) {
  object(document, "series");
  if (validatedSeries.has(document)) return document;
  integer(document.schemaVersion, "series.schemaVersion", 1);
  if (document.schemaVersion !== SCHEMA_VERSION) fail("series.schemaVersion", `unsupported version ${document.schemaVersion}`);
  string(document.id, "series.id");
  string(document.title, "series.title");
  integer(document.initialRating, "series.initialRating");
  array(document.contests, "series.contests");
  array(document.competitors, "series.competitors");

  const contestIds = new Set();
  document.contests.forEach((contest, i) => {
    const path = `series.contests[${i}]`;
    object(contest, path);
    string(contest.id, `${path}.id`);
    string(contest.title, `${path}.title`);
    string(contest.collection, `${path}.collection`);
    string(contest.startAt, `${path}.startAt`);
    if (Number.isNaN(Date.parse(contest.startAt))) fail(`${path}.startAt`, "expected ISO date-time");
    if (contestIds.has(contest.id)) fail(`${path}.id`, "duplicate contest id");
    contestIds.add(contest.id);
  });

  const competitorIds = new Set();
  document.competitors.forEach((competitor, i) => {
    const path = `series.competitors[${i}]`;
    object(competitor, path);
    string(competitor.id, `${path}.id`);
    text(competitor.school, `${path}.school`);
    string(competitor.member, `${path}.member`);
    integer(competitor.rank, `${path}.rank`, 1);
    integer(competitor.finalRating, `${path}.finalRating`);
    integer(competitor.contestsParticipated, `${path}.contestsParticipated`, 0);
    array(competitor.participations, `${path}.participations`);
    if (competitorIds.has(competitor.id)) fail(`${path}.id`, "duplicate competitor id");
    competitorIds.add(competitor.id);
    if (competitor.contestsParticipated !== competitor.participations.length) fail(`${path}.contestsParticipated`, "does not match participations length");
    let previousIndex = -1;
    let previousAfter;
    competitor.participations.forEach((participation, j) => {
      const partPath = `${path}.participations[${j}]`;
      object(participation, partPath);
      integer(participation.contestIndex, `${partPath}.contestIndex`, 0);
      integer(participation.contestRank, `${partPath}.contestRank`, 1);
      integer(participation.before, `${partPath}.before`);
      integer(participation.delta, `${partPath}.delta`);
      integer(participation.after, `${partPath}.after`);
      if (participation.contestIndex >= document.contests.length) fail(`${partPath}.contestIndex`, "out of range");
      if (participation.contestIndex <= previousIndex) fail(`${partPath}.contestIndex`, "must be strictly increasing");
      if (participation.before + participation.delta !== participation.after) fail(partPath, "before + delta must equal after");
      if (previousAfter !== undefined && participation.before !== previousAfter) fail(`${partPath}.before`, "rating is not continuous");
      previousIndex = participation.contestIndex;
      previousAfter = participation.after;
    });
    const expectedFinal = previousAfter ?? document.initialRating;
    if (competitor.finalRating !== expectedFinal) fail(`${path}.finalRating`, "does not match final participation");
  });
  validatedSeries.add(document);
  return document;
}

export function indexSeries(document) {
  validateSeries(document);
  if (indexedSeries.has(document)) return indexedSeries.get(document);
  const competitorById = new Map();
  const participantsByContest = document.contests.map(() => []);
  for (const competitor of document.competitors) {
    competitorById.set(competitor.id, competitor);
    for (const participation of competitor.participations) {
      participantsByContest[participation.contestIndex].push({ competitor, participation });
    }
  }
  for (const participants of participantsByContest) {
    participants.sort((a, b) => a.participation.contestRank - b.participation.contestRank || a.competitor.id.localeCompare(b.competitor.id));
  }
  const result = { competitorById, participantsByContest };
  indexedSeries.set(document, result);
  return result;
}

export function ratingTimeline(competitor, contests, initialRating) {
  const points = [];
  let cursor = 0;
  let rating = initialRating;
  for (let contestIndex = 0; contestIndex < contests.length; contestIndex += 1) {
    const participation = competitor.participations[cursor]?.contestIndex === contestIndex
      ? competitor.participations[cursor++]
      : null;
    if (participation) rating = participation.after;
    points.push({
      contestIndex,
      contest: contests[contestIndex],
      rating,
      participated: participation !== null,
      participation,
    });
  }
  return points;
}

export function carriedRatings(competitor, contestCount, initialRating) {
  const contests = Array.from({ length: contestCount }, (_, contestIndex) => ({ contestIndex }));
  return ratingTimeline(competitor, contests, initialRating).map((point) => point.rating);
}

export function ratingTier(rating) {
  if (rating >= 3000) return { className: "rating-legendary", color: "#000000", legendary: true };
  if (rating >= 2400) return { className: "rating-red", color: "#ff0000", legendary: false };
  if (rating >= 2100) return { className: "rating-orange", color: "#ffc000", legendary: false };
  if (rating >= 1900) return { className: "rating-purple", color: "#aa00aa", legendary: false };
  if (rating >= 1600) return { className: "rating-blue", color: "#0000ff", legendary: false };
  if (rating >= 1400) return { className: "rating-cyan", color: "#03a89e", legendary: false };
  if (rating >= 1200) return { className: "rating-green", color: "#008000", legendary: false };
  return { className: "rating-gray", color: "#808080", legendary: false };
}

export function searchCompetitors(competitors, query) {
  const terms = query.trim().toLocaleLowerCase().split(/\s+/u).filter(Boolean);
  if (!terms.length) return competitors;
  return competitors.filter((competitor) => {
    const text = `${competitor.member}\n${competitor.school}`.toLocaleLowerCase();
    return terms.every((term) => text.includes(term));
  });
}

export function formatDelta(delta) {
  return delta > 0 ? `+${delta}` : String(delta);
}

export function readQueryState(url) {
  const params = new URL(url, "http://localhost/").searchParams;
  return {
    series: params.get("series") || "",
    query: params.get("q") || "",
    contest: params.get("contest") || "",
    competitor: params.get("competitor") || "",
  };
}

export function writeQueryState(url, state) {
  const next = new URL(url, "http://localhost/");
  for (const [key, value] of [["series", state.series], ["q", state.query], ["contest", state.contest], ["competitor", state.competitor]]) {
    if (value) next.searchParams.set(key, value);
    else next.searchParams.delete(key);
  }
  return next;
}

export function createDataStore(indexUrl, fetchImpl = globalThis.fetch) {
  const indexPromise = fetchJson(indexUrl, fetchImpl).then(validateIndex);
  return {
    getIndex: () => indexPromise,
    async getSeries(id) {
      const index = await indexPromise;
      const entry = index.series.find((item) => item.id === id);
      if (!entry) throw new Error(`Unknown series: ${id}`);
      const series = validateSeries(await fetchJson(resolveDataUrl(entry.path, indexUrl), fetchImpl));
      if (series.id !== entry.id) throw new TypeError(`series.id: expected ${entry.id}, received ${series.id}`);
      return { entry, series, index: indexSeries(series) };
    },
  };
}
