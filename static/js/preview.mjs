import { fetchJson, resolveDataUrl } from "./data.mjs?v=20260904-20";

const SCHEMA_VERSION = 1;
const validatedPreviews = new WeakSet();

function fail(path, message) {
  throw new TypeError(`${path}: ${message}`);
}

function object(value, path) {
  if (!value || typeof value !== "object" || Array.isArray(value)) fail(path, "expected object");
}

function string(value, path) {
  if (typeof value !== "string" || !value) fail(path, "expected non-empty string");
}

function array(value, path) {
  if (!Array.isArray(value)) fail(path, "expected array");
}

function integer(value, path, minimum = Number.MIN_SAFE_INTEGER) {
  if (!Number.isSafeInteger(value) || value < minimum) fail(path, `expected integer >= ${minimum}`);
}

function rating(value, path) {
  if (value !== null && (typeof value !== "number" || !Number.isFinite(value))) {
    fail(path, "expected a finite number or null");
  }
}

function validateMedals(medals, path) {
  object(medals, path);
  for (const medal of ["gold", "silver", "bronze"]) integer(medals[medal], `${path}.${medal}`, 0);
}

export function validatePreview(document) {
  object(document, "preview");
  if (validatedPreviews.has(document)) return document;
  integer(document.schemaVersion, "preview.schemaVersion", 1);
  if (document.schemaVersion !== SCHEMA_VERSION) fail("preview.schemaVersion", `unsupported version ${document.schemaVersion}`);
  for (const key of ["seriesId", "seriesTitle", "id", "title", "sortAt", "snapshotDate", "matchingPolicy"]) {
    string(document[key], `preview.${key}`);
  }
  if (Number.isNaN(Date.parse(document.sortAt))) fail("preview.sortAt", "expected ISO date-time");
  object(document.teamSource, "preview.teamSource");
  for (const key of ["title", "url", "note"]) string(document.teamSource[key], `preview.teamSource.${key}`);
  array(document.metricSources, "preview.metricSources");
  if (!document.metricSources.length) fail("preview.metricSources", "expected at least one source");
  const metricIds = new Set();
  document.metricSources.forEach((source, index) => {
    const path = `preview.metricSources[${index}]`;
    object(source, path);
    for (const key of ["id", "title", "url"]) string(source[key], `${path}.${key}`);
    if (metricIds.has(source.id)) fail(`${path}.id`, "duplicate metric id");
    metricIds.add(source.id);
  });
  array(document.teams, "preview.teams");
  if (!document.teams.length) fail("preview.teams", "expected at least one team");
  const teamIds = new Set();
  document.teams.forEach((team, teamIndex) => {
    const path = `preview.teams[${teamIndex}]`;
    object(team, path);
    for (const key of ["id", "school", "name"]) string(team[key], `${path}.${key}`);
    integer(team.sourceIndex, `${path}.sourceIndex`, 0);
    if (team.sourceIndex !== teamIndex) fail(`${path}.sourceIndex`, "must preserve source order");
    if (teamIds.has(team.id)) fail(`${path}.id`, "duplicate team id");
    teamIds.add(team.id);
    array(team.members, `${path}.members`);
    if (!team.members.length) fail(`${path}.members`, "expected at least one member");
    const memberRatingValues = new Map([...metricIds].map((id) => [id, []]));
    const medalTotals = { gold: 0, silver: 0, bronze: 0 };
    team.members.forEach((member, memberIndex) => {
      const memberPath = `${path}.members[${memberIndex}]`;
      object(member, memberPath);
      string(member.name, `${memberPath}.name`);
      object(member.ratings, `${memberPath}.ratings`);
      for (const id of metricIds) {
        rating(member.ratings[id], `${memberPath}.ratings.${id}`);
        if (member.ratings[id] !== null) memberRatingValues.get(id).push(member.ratings[id]);
      }
      validateMedals(member.medals, `${memberPath}.medals`);
      for (const medal of Object.keys(medalTotals)) medalTotals[medal] += member.medals[medal];
    });
    object(team.ratings, `${path}.ratings`);
    for (const id of metricIds) {
      rating(team.ratings[id], `${path}.ratings.${id}`);
      const values = memberRatingValues.get(id);
      const expected = values.length ? Math.max(...values) : null;
      if (team.ratings[id] !== expected) fail(`${path}.ratings.${id}`, "must equal the highest member value");
    }
    validateMedals(team.medals, `${path}.medals`);
    for (const medal of Object.keys(medalTotals)) {
      if (team.medals[medal] !== medalTotals[medal]) fail(`${path}.medals.${medal}`, "must equal the member total");
    }
  });
  validatedPreviews.add(document);
  return document;
}

export function listPreviewSchools(teams) {
  return [...new Set(teams.map(({ school }) => school))].sort((a, b) => a.localeCompare(b, "zh-CN"));
}

export function searchPreviewTeams(teams, query, schools = []) {
  const terms = query.trim().toLocaleLowerCase().split(/\s+/u).filter(Boolean);
  const selectedSchools = new Set(schools);
  if (!terms.length && !selectedSchools.size) return teams;
  return teams.filter((team) => {
    if (selectedSchools.size && !selectedSchools.has(team.school)) return false;
    const text = `${team.school}\n${team.name}\n${team.members.map(({ name }) => name).join("\n")}`.toLocaleLowerCase();
    return terms.every((term) => text.includes(term));
  });
}

export function previewRatingValue(metricId, value) {
  return metricId === "cpcfinder" && value === 0 ? null : value;
}

function comparePowerValues(left, right) {
  if (left === null && right === null) return 0;
  if (left === null) return -1;
  if (right === null) return 1;
  return left - right;
}

function compareMedals(left, right) {
  for (const medal of ["gold", "silver", "bronze"]) {
    const compared = left[medal] - right[medal];
    if (compared) return compared;
  }
  return 0;
}

function countStrictlyLower(teams, valueOf, compare) {
  const ordered = teams
    .map((team) => ({ id: team.id, value: valueOf(team), sourceIndex: team.sourceIndex }))
    .sort((left, right) => compare(left.value, right.value) || left.sourceIndex - right.sourceIndex);
  const counts = new Map();
  let groupStart = 0;
  ordered.forEach((item, index) => {
    if (index && compare(item.value, ordered[index - 1].value)) groupStart = index;
    counts.set(item.id, groupStart);
  });
  return counts;
}

function competitionRanks(teams, valueOf, compare, skipNull = false) {
  const ordered = teams
    .map((team) => ({ id: team.id, value: valueOf(team), sourceIndex: team.sourceIndex }))
    .filter(({ value }) => !skipNull || value !== null)
    .sort((left, right) => compare(right.value, left.value) || left.sourceIndex - right.sourceIndex);
  const ranks = new Map(teams.map(({ id }) => [id, null]));
  let previousValue;
  let rank = 0;
  ordered.forEach((item, index) => {
    if (!index || compare(item.value, previousValue)) rank = index + 1;
    ranks.set(item.id, rank);
    previousValue = item.value;
  });
  return ranks;
}

export function buildPreviewRanks(teams, metricIds = Object.keys(teams[0]?.ratings ?? {})) {
  const ratingRanks = new Map(metricIds.map((id) => [
    id,
    competitionRanks(teams, (team) => previewRatingValue(id, team.ratings[id] ?? null), comparePowerValues, true),
  ]));
  const medalRanks = competitionRanks(teams, (team) => team.medals, compareMedals);
  return new Map(teams.map((team) => [team.id, {
    ratings: Object.fromEntries(metricIds.map((id) => [id, ratingRanks.get(id).get(team.id)])),
    medals: medalRanks.get(team.id),
  }]));
}

function comparePowerVectors(left, right, order = "desc") {
  const direction = order === "asc" ? 1 : -1;
  for (let index = 0; index < left.length; index += 1) {
    const compared = (left[index] - right[index]) * direction;
    if (compared) return compared;
  }
  return 0;
}

export function buildPreviewPower(teams, metricIds = Object.keys(teams[0]?.ratings ?? {})) {
  const dimensions = [
    ...metricIds.map((id) => countStrictlyLower(
      teams,
      (team) => previewRatingValue(id, team.ratings[id] ?? null),
      comparePowerValues,
    )),
    countStrictlyLower(teams, (team) => team.medals, compareMedals),
  ];
  const power = new Map(teams.map((team) => {
    const counts = dimensions.map((values) => values.get(team.id));
    return [team.id, { counts, vector: [...counts].sort((left, right) => right - left), rank: 0 }];
  }));
  const ranked = [...teams].sort((left, right) => (
    comparePowerVectors(power.get(left.id).vector, power.get(right.id).vector)
    || left.sourceIndex - right.sourceIndex
  ));
  let previousVector = null;
  let rank = 0;
  ranked.forEach((team, index) => {
    const entry = power.get(team.id);
    if (previousVector === null || comparePowerVectors(entry.vector, previousVector)) rank = index + 1;
    entry.rank = rank;
    previousVector = entry.vector;
  });
  return power;
}

function compareNullableNumber(left, right, order) {
  if (left === null && right === null) return 0;
  if (left === null) return 1;
  if (right === null) return -1;
  return order === "asc" ? left - right : right - left;
}

export function sortPreviewTeams(teams, sort, order = "desc", previewPower = null) {
  const direction = order === "asc" ? 1 : -1;
  const power = sort === "power" && !previewPower ? buildPreviewPower(teams) : previewPower;
  return [...teams].sort((left, right) => {
    let compared = 0;
    if (sort === "school" || sort === "name") {
      compared = left[sort].localeCompare(right[sort], "zh-CN") * direction;
    } else if (sort === "members") {
      compared = left.members.map(({ name }) => name).join("/").localeCompare(
        right.members.map(({ name }) => name).join("/"), "zh-CN",
      ) * direction;
    } else if (sort === "medals") {
      for (const medal of ["gold", "silver", "bronze"]) {
        compared = (left.medals[medal] - right.medals[medal]) * direction;
        if (compared) break;
      }
    } else if (sort === "power") {
      compared = comparePowerVectors(
        power.get(left.id).vector,
        power.get(right.id).vector,
        order,
      );
    } else {
      compared = compareNullableNumber(
        previewRatingValue(sort, left.ratings[sort] ?? null),
        previewRatingValue(sort, right.ratings[sort] ?? null),
        order,
      );
    }
    return compared || left.sourceIndex - right.sourceIndex;
  });
}

export function buildPreviewSchoolRanks(sortedTeams, sort) {
  if (["school", "name", "members"].includes(sort)) return new Map();
  const rankedSchools = new Set();
  const ranks = new Map();
  for (const team of sortedTeams) {
    if (rankedSchools.has(team.school)) continue;
    rankedSchools.add(team.school);
    ranks.set(team.id, rankedSchools.size);
  }
  return ranks;
}

export function readPreviewQuery(url) {
  const params = new URL(url, "http://localhost/").searchParams;
  return {
    previewSort: params.get("previewSort") || "power",
    previewOrder: params.get("previewOrder") === "asc" ? "asc" : "desc",
  };
}

export function writePreviewQuery(url, query) {
  const next = new URL(url, "http://localhost/");
  if (query.view !== "preview") {
    for (const key of ["previewSort", "previewOrder"]) next.searchParams.delete(key);
    return next;
  }
  next.searchParams.set("view", "preview");
  if (query.sort && query.sort !== "power") next.searchParams.set("previewSort", query.sort);
  else next.searchParams.delete("previewSort");
  if (query.order === "asc") next.searchParams.set("previewOrder", "asc");
  else next.searchParams.delete("previewOrder");
  return next;
}

export function createPreviewStore(indexUrl, fetchImpl = globalThis.fetch) {
  return {
    async getSeries(entry) {
      if (!entry.previewPath) throw new Error(`Series has no preview data: ${entry.id}`);
      const preview = validatePreview(await fetchJson(resolveDataUrl(entry.previewPath, indexUrl), fetchImpl));
      if (preview.seriesId !== entry.id) fail("preview.seriesId", `expected ${entry.id}, received ${preview.seriesId}`);
      return preview;
    },
  };
}
