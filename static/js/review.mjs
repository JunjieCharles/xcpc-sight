import { fetchJson, resolveDataUrl } from "./data.mjs?v=20260907-42";
import { buildPreviewPower, buildPreviewRanks, sortPreviewTeams, searchPreviewTeams } from "./preview.mjs?v=20260907-42";

const validated = new WeakMap();
const analyses = new WeakMap();

export function validateReview(document, previews) {
  if (previews && validated.get(document) === previews) return document;
  const fail = (path, message) => { throw new TypeError(`review.${path}: ${message}`); };
  if (!document || document.schemaVersion !== 1) fail("schemaVersion", "expected 1");
  if (!Array.isArray(previews) || !previews.length) fail("previews", "expected previews");
  if (previews.some(p => p.seriesId !== document.seriesId)) fail("seriesId", "preview series mismatch");
  if (!Array.isArray(document.contests) || !document.contests.length) fail("contests", "expected nonempty array");
  const ids = new Set();
  const previewIds = new Set();
  for (const [i, contest] of document.contests.entries()) {
    const path = `contests[${i}]`;
    if (!contest || typeof contest !== "object") fail(path, "expected object");
    for (const key of ["id", "previewId", "title", "startAt"]) {
      if (typeof contest[key] !== "string" || !contest[key]) fail(`${path}.${key}`, "expected string");
    }
    if (Number.isNaN(Date.parse(contest.startAt))) fail(`${path}.startAt`, "invalid date");
    if (ids.has(contest.id) || previewIds.has(contest.previewId)) fail(path, "duplicate contest or preview ID");
    ids.add(contest.id);
    previewIds.add(contest.previewId);
    const preview = previews.find(p => p.id === contest.previewId);
    if (!preview) fail(`${path}.previewId`, "unknown preview");
    if (!contest.source || !["title", "url"].every(k => typeof contest.source[k] === "string" && contest.source[k])) {
      fail(`${path}.source`, "expected source title and URL");
    }
    if (!Array.isArray(contest.teams)) fail(`${path}.teams`, "expected array");
    const rosterIds = new Set(preview.teams.map(t => t.id));
    const resultIds = new Set();
    for (const [j, team] of contest.teams.entries()) {
      const teamPath = `${path}.teams[${j}]`;
      if (!team || !rosterIds.delete(team.previewTeamId)) fail(teamPath, "unknown or duplicate preview team");
      if (typeof team.resultTeamId !== "string" || !team.resultTeamId || resultIds.has(team.resultTeamId)) {
        fail(teamPath, "missing or duplicate result team ID");
      }
      resultIds.add(team.resultTeamId);
      if (typeof team.hasActivity !== "boolean") fail(teamPath, "expected hasActivity boolean");
      if (team.hasActivity
        ? !Number.isSafeInteger(team.actualRank) || team.actualRank < 1
        : team.actualRank !== null) fail(teamPath, "rank must be positive for active teams, otherwise null");
    }
    if (rosterIds.size) fail(`${path}.teams`, "missing preview teams; matching failures are not absences");
  }
  validated.set(document, previews);
  return document;
}

export function createReviewStore(indexUrl, fetchImpl = globalThis.fetch) {
  return {
    async getSeries(entry, previews) {
      if (!entry.reviewPath) return null;
      return validateReview(await fetchJson(resolveDataUrl(entry.reviewPath, indexUrl), fetchImpl), previews);
    },
  };
}

function averageRanks(values) {
  const ordered = values.map((value, index) => ({ value, index })).sort((a, b) => a.value - b.value);
  const ranks = new Array(values.length);
  for (let start = 0; start < ordered.length;) {
    let end = start + 1;
    while (end < ordered.length && ordered[end].value === ordered[start].value) end += 1;
    const rank = (start + 1 + end) / 2;
    for (let i = start; i < end; i += 1) ranks[ordered[i].index] = rank;
    start = end;
  }
  return ranks;
}

// Pearson correlation of average ranks, including ties on either side.
export function spearmanRho(pairs) {
  if (!Array.isArray(pairs) || pairs.some(pair => !Array.isArray(pair) || pair.length !== 2
      || pair.some(value => typeof value !== "number" || !Number.isFinite(value)))) {
    throw new TypeError("Spearman rho requires finite numeric pairs");
  }
  if (pairs.length < 2) return { value: null, reason: "有效队伍不足两支" };
  const x = averageRanks(pairs.map(pair => pair[0]));
  const y = averageRanks(pairs.map(pair => pair[1]));
  const mean = (pairs.length + 1) / 2;
  let covariance = 0, varianceX = 0, varianceY = 0;
  for (let i = 0; i < pairs.length; i += 1) {
    const dx = x[i] - mean, dy = y[i] - mean;
    covariance += dx * dy;
    varianceX += dx * dx;
    varianceY += dy * dy;
  }
  const denominator = Math.sqrt(varianceX * varianceY);
  return denominator
    ? { value: Math.max(-1, Math.min(1, covariance / denominator)), reason: null }
    : { value: null, reason: "前瞻或实际排名全部并列" };
}

function ranks(teams, compare) {
  const sorted = [...teams].sort(compare);
  const result = new Map();
  let rank = 0;
  sorted.forEach((team, i) => {
    if (!i || compare(team, sorted[i - 1])) rank = i + 1;
    result.set(team.id, rank);
  });
  return result;
}

function compareMedals(a, b) {
  return a.gold - b.gold || a.silver - b.silver || a.bronze - b.bronze;
}

export function buildReviewAnalysis(preview, contest, metric = "power") {
  const metricIds = preview.metricSources.map(s => s.id);
  if (!["power", "medals", ...metricIds].includes(metric)) throw new TypeError(`Unknown review metric: ${metric}`);
  let cache = analyses.get(preview);
  if (!cache) { cache = new WeakMap(); analyses.set(preview, cache); }
  if (!cache.has(contest)) cache.set(contest, new Map());
  const byMetric = cache.get(contest);
  if (byMetric.has(metric)) return byMetric.get(metric);
  const power = buildPreviewPower(preview.teams, metricIds);
  const originalRanks = metric === "power" ? null : buildPreviewRanks(preview.teams, metricIds);
  const results = new Map(contest.teams.map(t => [t.previewTeamId, t]));
  const active = preview.teams.filter(t => results.get(t.id)?.hasActivity);
  const teams = active.filter(t => metric === "power"
    ? power.get(t.id).vector.some(value => value !== 0)
    : t.ratings[metric === "medals" ? "cpcfinder" : metric] != null);
  const compare = metric === "power"
    ? (a, b) => power.get(a.id).rank - power.get(b.id).rank
    : metric === "medals"
      ? (a, b) => compareMedals(b.medals, a.medals)
      : (a, b) => b.ratings[metric] - a.ratings[metric];
  const predicted = ranks(teams, compare);
  const actual = ranks(teams, (a, b) => results.get(a.id).actualRank - results.get(b.id).actualRank);
  const rows = teams.map(team => ({
    ...team,
    previewRank: predicted.get(team.id),
    actualRank: actual.get(team.id),
    originalPowerRank: power.get(team.id).rank,
    originalPreviewRank: metric === "power" ? power.get(team.id).rank
      : metric === "medals" ? originalRanks.get(team.id).medals : originalRanks.get(team.id).ratings[metric],
    originalActualRank: results.get(team.id).actualRank,
    change: predicted.get(team.id) - actual.get(team.id),
    growth: Math.log10(predicted.get(team.id) / actual.get(team.id)),
  }));
  const analysis = {
    rows, metric, power, activeCount: active.length,
    coverage: active.length ? rows.length / active.length : null,
    agreement: spearmanRho(rows.map(t => [t.previewRank, t.actualRank])),
  };
  byMetric.set(metric, analysis);
  return analysis;
}

export function sortReviewRows(analysis, sort = "actualRank", order = "asc") {
  if (["school", "name", "members"].includes(sort)) return sortPreviewTeams(analysis.rows, sort, order);
  if (sort === "metric") return sortPreviewTeams(analysis.rows, analysis.metric, order, analysis.power);
  const key = ["previewRank", "actualRank", "change", "growth"].includes(sort) ? sort : "actualRank";
  return [...analysis.rows].sort((a, b) => (
    (a[key] - b[key]) * (order === "desc" ? -1 : 1)
    || a.school.localeCompare(b.school, "zh-CN") || a.sourceIndex - b.sourceIndex
  ));
}

export function selectReviewRows(analysis, { sort, order, query = "", schools = [] } = {}) {
  return searchPreviewTeams(sortReviewRows(analysis, sort, order), query, schools);
}

export function readReviewQuery(url) {
  const params = new URL(url, "http://localhost/").searchParams;
  const sort = params.get("reviewSort");
  return {
    reviewContest: params.get("reviewContest") || "",
    reviewMetric: params.get("reviewMetric") || "power",
    reviewSort: ["school", "name", "members", "metric", "previewRank", "actualRank", "change", "growth"].includes(sort) ? sort : "actualRank",
    reviewOrder: params.get("reviewOrder") === "desc" ? "desc" : "asc",
  };
}

export function writeReviewQuery(url, query) {
  const next = new URL(url, "http://localhost/");
  for (const key of ["reviewContest", "reviewMetric", "reviewSort", "reviewOrder"]) next.searchParams.delete(key);
  if (query.view === "review") {
    next.searchParams.set("view", "review");
    if (query.contest) next.searchParams.set("reviewContest", query.contest);
    if (query.metric && query.metric !== "power") next.searchParams.set("reviewMetric", query.metric);
    if (query.sort && query.sort !== "actualRank") next.searchParams.set("reviewSort", query.sort);
    if (query.order === "desc") next.searchParams.set("reviewOrder", "desc");
  } else if (next.searchParams.get("view") === "review") next.searchParams.delete("view");
  return next;
}
