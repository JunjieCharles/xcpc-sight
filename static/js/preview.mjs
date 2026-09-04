import { fetchJson, resolveDataUrl } from "./data.mjs?v=20260904-1";

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

function compareNullableNumber(left, right, order) {
  if (left === null && right === null) return 0;
  if (left === null) return 1;
  if (right === null) return -1;
  return order === "asc" ? left - right : right - left;
}

export function sortPreviewTeams(teams, sort, order = "desc") {
  const direction = order === "asc" ? 1 : -1;
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
    } else {
      compared = compareNullableNumber(left.ratings[sort] ?? null, right.ratings[sort] ?? null, order);
    }
    return compared || left.sourceIndex - right.sourceIndex;
  });
}

export function readPreviewQuery(url) {
  const params = new URL(url, "http://localhost/").searchParams;
  return {
    previewSort: params.get("previewSort") || "xcpcrating",
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
  if (query.sort && query.sort !== "xcpcrating") next.searchParams.set("previewSort", query.sort);
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
