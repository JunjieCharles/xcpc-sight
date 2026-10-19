import { fetchJson, resolveDataUrl } from "./data.mjs?v=20261019-74";

const SCHEMA_VERSION = 1;
const validatedPreviews = new WeakSet();
const ACHIEVEMENT_PRIORITY = { participant: 0, bronze: 1, silver: 2, gold: 3 };

export function formatPreviewTime(preview) {
  if (preview.hideContestTime) return "";
  if (preview.id === "icpc-2026-preliminary-1") return "比赛时间：2026年9月6日 13:00-18:00";
  const date = new Intl.DateTimeFormat("zh-CN", { timeZone: "Asia/Shanghai", dateStyle: "long" });
  const time = new Intl.DateTimeFormat("zh-CN", { timeZone: "Asia/Shanghai", timeStyle: "short" });
  const start = new Date(preview.sortAt);
  let label = `比赛时间：${date.format(start)} ${time.format(start)}`;
  if (preview.endAt) {
    const end = new Date(preview.endAt);
    label += `–${date.format(start) === date.format(end) ? "" : date.format(end) + " "}${time.format(end)}`;
  }
  return label;
}

export function normalizedLseRating(values) {
  values.forEach((value, index) => {
    if (!Number.isFinite(value)) fail(`team ratings[${index}]`, "expected a finite number");
  });
  if (!values.length) return null;
  const peak = Math.max(...values);
  const weights = values.map(value => 10 ** ((value - peak) / 400)).sort((a, b) => a - b);
  return peak + 400 * Math.log10(weights.reduce((sum, value) => sum + value, 0) / values.length);
}

export function previewHistoryTitle(record) {
  const title = record.contestTitle;
  const competition = record.contestId.startsWith("ccpc") ? "CCPC" : "ICPC";
  const editionText = title.match(/第\s*(\d+|十一)\s*届/u)?.[1]
    ?? title.match(/(\d+)(?:st|nd|rd|th)\s+ICPC/u)?.[1];
  const edition = editionText === "十一" ? 11 : Number(editionText);
  const place = /总决赛/u.test(title) ? (competition === "ICPC" ? "EC-Final" : "Final")
    : title.match(/(?:区域赛|竞赛)([\u4e00-\u9fff]{2,4})站/u)?.[1]
      ?? title.match(/区域赛[（(]([^）)]+)[）)]/u)?.[1]
      ?? (title.includes("Hong Kong Regional") ? "香港" : null);
  if (!edition || !place) return title;
  const suffix = edition % 100 >= 11 && edition % 100 <= 13 ? "th"
    : ({ 1: "st", 2: "nd", 3: "rd" }[edition % 10] || "th");
  return `${edition}${suffix} ${competition} ${place}`;
}

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

function finiteNumber(value, path, minimum = Number.NEGATIVE_INFINITY) {
  if (typeof value !== "number" || !Number.isFinite(value) || value < minimum) {
    fail(path, `expected a finite number >= ${minimum}`);
  }
}

function validateAchievements(achievements, path) {
  array(achievements, path);
  let previousOrder = null;
  achievements.forEach((achievement, index) => {
    const achievementPath = `${path}[${index}]`;
    object(achievement, achievementPath);
    if (!["noi", "ioi"].includes(achievement.competition)) {
      fail(`${achievementPath}.competition`, "expected noi or ioi");
    }
    integer(achievement.year, `${achievementPath}.year`, 1984);
    string(achievement.medal, `${achievementPath}.medal`);
    if (!(achievement.medal in ACHIEVEMENT_PRIORITY)) {
      fail(`${achievementPath}.medal`, "expected gold, silver, bronze, or participant");
    }
    if (achievement.competition === "noi") {
      if (achievement.medal === "participant") fail(`${achievementPath}.medal`, "NOI requires a medal");
      integer(achievement.rank, `${achievementPath}.rank`, 1);
      finiteNumber(achievement.score, `${achievementPath}.score`, 0);
      finiteNumber(achievement.maxScore, `${achievementPath}.maxScore`, 1);
      if (achievement.score > achievement.maxScore) fail(`${achievementPath}.score`, "exceeds maxScore");
    } else if (achievement.medal === "participant") {
      if (achievement.rank !== undefined || achievement.score !== undefined || achievement.maxScore !== undefined) {
        fail(achievementPath, "unawarded IOI participation must not contain result fields");
      }
    } else {
      integer(achievement.rank, `${achievementPath}.rank`, 1);
      finiteNumber(achievement.score, `${achievementPath}.score`, 0);
      finiteNumber(achievement.maxScore, `${achievementPath}.maxScore`, 1);
      if (achievement.score > achievement.maxScore) fail(`${achievementPath}.score`, "exceeds maxScore");
    }
    const order = achievement.year * 2 + (achievement.competition === "ioi" ? 1 : 0);
    if (previousOrder !== null && order < previousOrder) fail(achievementPath, "must be chronological");
    previousOrder = order;
  });
}

export function bestAchievementMedal(achievements, competition) {
  let best = null;
  for (const achievement of achievements) {
    if (achievement.competition !== competition) continue;
    if (best === null || ACHIEVEMENT_PRIORITY[achievement.medal] > ACHIEVEMENT_PRIORITY[best]) {
      best = achievement.medal;
    }
  }
  return best;
}

export function achievementDisplayParts(achievement) {
  const competition = `${achievement.year} ${achievement.competition.toUpperCase()}`;
  if (achievement.medal === "participant") {
    return [competition];
  }
  const medal = { gold: "金牌", silver: "银牌", bronze: "铜牌" }[achievement.medal];
  return [
    competition,
    `${medal}#${achievement.rank}`,
    `${achievement.score} / ${achievement.maxScore}`,
  ];
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
  if (document.contestStage !== undefined && !["preliminary", "regional"].includes(document.contestStage)) {
    fail("preview.contestStage", "expected preliminary or regional");
  }
  if (document.unlisted !== undefined && typeof document.unlisted !== "boolean") {
    fail("preview.unlisted", "expected boolean");
  }
  if (document.hostSchool !== undefined) {
    string(document.hostSchool, "preview.hostSchool");
    if (!document.hostSchool.trim()) fail("preview.hostSchool", "expected non-blank school name");
  }
  if (document.hideContestTime !== undefined && typeof document.hideContestTime !== "boolean") {
    fail("preview.hideContestTime", "expected boolean");
  }
  const aggregation = document.ratingAggregation === undefined ? "max" : document.ratingAggregation;
  if (!["max", "normalized-lse"].includes(aggregation)) fail("preview.ratingAggregation", "unsupported aggregation");
  for (const key of ["seriesId", "seriesTitle", "id", "title", "sortAt", "snapshotDate", "matchingPolicy"]) {
    string(document[key], `preview.${key}`);
  }
  if (Number.isNaN(Date.parse(document.sortAt))) fail("preview.sortAt", "expected ISO date-time");
  if (document.endAt !== undefined) {
    string(document.endAt, "preview.endAt");
    if (!Number.isFinite(Date.parse(document.endAt)) || Date.parse(document.endAt) <= Date.parse(document.sortAt)) {
      fail("preview.endAt", "expected a date-time after sortAt");
    }
  }
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
  if (document.onlineContests !== undefined) {
    array(document.onlineContests, "preview.onlineContests");
    const expected = ["icpc2026preliminary-1", "icpc2026preliminary-2", "ccpc2026preliminary"];
    if (document.onlineContests.length !== 3) fail("preview.onlineContests", "expected three contests");
    document.onlineContests.forEach((contest, i) => {
      object(contest, "preview.onlineContests.entry");
      if (contest.id !== expected[i]) fail("preview.onlineContests", "expected ICPC1 / ICPC2 / CCPC order");
      string(contest.title, "preview.onlineContests.title");
    });
  }
  if (document.powerMetrics !== undefined) {
    array(document.powerMetrics, "preview.powerMetrics");
    const allowed = new Set([...metricIds, "medals", ...(document.onlineContests ? ["onlineRanks"] : [])]);
    if (!document.powerMetrics.length || new Set(document.powerMetrics).size !== document.powerMetrics.length
      || document.powerMetrics.some(id => !allowed.has(id))) fail("preview.powerMetrics", "invalid dimensions");
  }
  array(document.teams, "preview.teams");
  if (!document.teams.length) fail("preview.teams", "expected at least one team");
  const teamIds = new Set();
  document.teams.forEach((team, teamIndex) => {
    const path = `preview.teams[${teamIndex}]`;
    object(team, path);
    for (const key of ["id", "school", "name"]) string(team[key], `${path}.${key}`);
    integer(team.sourceIndex, `${path}.sourceIndex`, 0);
    if (team.excluded !== undefined && typeof team.excluded !== "boolean") {
      fail(`${path}.excluded`, "expected boolean");
    }
    if (team.sourceIndex !== teamIndex) fail(`${path}.sourceIndex`, "must preserve source order");
    if (teamIds.has(team.id)) fail(`${path}.id`, "duplicate team id");
    teamIds.add(team.id);
    array(team.members, `${path}.members`);
    if (!team.members.length) fail(`${path}.members`, "expected at least one member");
    if (team.previousSeasonHistory !== undefined) {
      array(team.previousSeasonHistory, `${path}.previousSeasonHistory`);
      const historyIds = new Set();
      team.previousSeasonHistory.forEach((record, index) => {
        const historyPath = `${path}.previousSeasonHistory[${index}]`;
        object(record, historyPath);
        for (const key of ["contestId", "contestTitle", "startAt", "teamId", "teamName"]) {
          string(record[key], `${historyPath}.${key}`);
        }
        if (!Number.isFinite(Date.parse(record.startAt))) fail(historyPath, "invalid startAt");
        integer(record.rank, `${historyPath}.rank`, 1);
        integer(record.matchedMembers, `${historyPath}.matchedMembers`, 1);
        if (record.matchedMembers > team.members.length) fail(historyPath, "too many matched members");
        if (![null, "gold", "silver", "bronze"].includes(record.medal)) fail(historyPath, "invalid medal");
        const key = JSON.stringify([record.contestId, record.teamId]);
        if (historyIds.has(key)) fail(historyPath, "duplicate history team");
        historyIds.add(key);
      });
    }
    const memberRatingValues = new Map([...metricIds].map((id) => [id, []]));
    const medalTotals = { gold: 0, silver: 0, bronze: 0 };
    team.members.forEach((member, memberIndex) => {
      const memberPath = `${path}.members[${memberIndex}]`;
      object(member, memberPath);
      string(member.name, `${memberPath}.name`);
      validateAchievements(member.achievements, `${memberPath}.achievements`);
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
      const useLse = aggregation === "normalized-lse" && id !== "cpcfinder";
      const expected = useLse ? normalizedLseRating(values) : values.length ? Math.max(...values) : null;
      const actual = team.ratings[id];
      const matches = actual === expected || (useLse && actual !== null && expected !== null
        && Math.abs(actual - expected) <= 1e-9);
      if (!matches) fail(`${path}.ratings.${id}`, useLse
        ? "must equal normalized LSE of member values" : "must equal the highest member value");
    }
    if (document.onlineContests !== undefined) {
      const checkRanks = (values, rankPath) => {
        array(values, rankPath);
        if (values.length !== 3) fail(rankPath, "expected three ranks");
        values.forEach(value => { if (value !== null) integer(value, rankPath, 1); });
      };
      checkRanks(team.onlineRanks, `${path}.onlineRanks`);
      team.members.forEach(member => checkRanks(member.onlineRanks, `${path}.members.onlineRanks`));
      team.onlineRanks.forEach((rank, slot) => {
        const values = team.members.map(member => member.onlineRanks[slot]).filter(value => value !== null);
        if (rank !== (values.length ? Math.min(...values) : null)) fail(`${path}.onlineRanks`, "must equal best member rank");
      });
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

export function searchPreviewTeams(teams, query, schools = [], teamType = "all") {
  const terms = query.trim().toLocaleLowerCase().split(/\s+/u).filter(Boolean);
  const selectedSchools = new Set(schools);
  if (!terms.length && !selectedSchools.size && !["official", "starred"].includes(teamType)) return teams;
  return teams.filter((team) => {
    if (teamType === "official" && team.excluded) return false;
    if (teamType === "starred" && !team.excluded) return false;
    if (selectedSchools.size && !selectedSchools.has(team.school)) return false;
    const text = `${team.school}\n${team.name}\n${team.members.map(({ name }) => name).join("\n")}`.toLocaleLowerCase();
    return terms.every((term) => text.includes(term));
  });
}

export function previewRatingValue(metricId, value) {
  // Normalize only for comprehensive power; display and rank the stored value.
  return metricId === "cpcfinder" && value === 0 ? null : value;
}

function comparePowerValues(left, right) {
  if (left === null && right === null) return 0;
  if (left === null) return -1;
  if (right === null) return 1;
  return left - right;
}

export function compareOnlineRanks(left, right) {
  const values = ranks => (ranks ?? [null, null, null]).map(rank => rank ?? Infinity).sort((a, b) => a - b);
  const a = values(left), b = values(right);
  for (let i = 0; i < 3; i += 1) {
    if (a[i] !== b[i]) return a[i] < b[i] ? 1 : -1;
  }
  return 0;
}

// Quotas use all official teams; missing results never become a numeric cutoff.
export function previewOfficialTeamCount(preview) {
  return preview.summaryOnly ? preview.officialTeamCount
    : preview.teams.filter(team => !team.excluded).length;
}

export function buildPreviewCutoffs(preview) {
  const teams = preview.teams.filter(team => !team.excluded)
    .sort((a, b) => -compareOnlineRanks(a.onlineRanks, b.onlineRanks));
  const schools = new Set();
  const schoolTeams = teams.filter(team => {
    if (schools.has(team.school)) return false;
    schools.add(team.school);
    return true;
  });
  const best = team => {
    const ranks = (team?.onlineRanks ?? []).filter(rank => rank !== null);
    return ranks.length ? Math.min(...ranks) : null;
  };
  const n = teams.length;
  const gold = Math.ceil(n / 10);
  const silver = gold + Math.ceil(n * 2 / 10);
  const bronze = silver + Math.ceil(n * 3 / 10);
  return {
    cup: best(schoolTeams[2]), gold: best(teams[gold - 1]),
    silver: best(teams[silver - 1]), bronze: best(teams[bronze - 1]),
  };
}

export function previewContestDate(preview) {
  if (preview.hideContestTime) return null;
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit", day: "2-digit",
  }).format(new Date(preview.sortAt));
}

export function previewOrganization(preview) {
  return preview.id.match(/^(icpc|ccpc)-/i)?.[1].toUpperCase()
    ?? preview.title?.match(/ICPC|CCPC/i)?.[0].toUpperCase() ?? null;
}

export function selectPreviewContest(previews, requestedId, rememberedId, now = new Date()) {
  for (const id of [requestedId, rememberedId]) {
    const selected = previews.find(preview => preview.id === id);
    if (selected) return selected;
  }
  const visible = previews.filter(preview => !preview.unlisted);
  const today = previewContestDate({ sortAt: now });
  const priority = preview => ({ ICPC: 0, CCPC: 1 })[previewOrganization(preview)] ?? 2;
  const tie = (a, b) => priority(a) - priority(b) || a.id.localeCompare(b.id);
  const dated = visible.filter(preview => previewContestDate(preview));
  const upcoming = dated.filter(preview => previewContestDate(preview) >= today);
  if (upcoming.length) return upcoming.sort((a, b) =>
    previewContestDate(a).localeCompare(previewContestDate(b)) || tie(a, b))[0];
  if (dated.length) return dated.sort((a, b) =>
    previewContestDate(b).localeCompare(previewContestDate(a)) || tie(a, b))[0];
  return visible.sort(tie)[0] ?? null;
}

export function previewNavigationGroups(previews, currentId, summaries = []) {
  const ids = new Set(previews.map(p => p.id));
  const visible = [...previews.filter(preview => !preview.unlisted || preview.id === currentId),
    ...summaries.filter(summary => !ids.has(summary.id)).map(summary => ({ ...summary, summaryOnly: true }))];
  return {
    online: visible.filter(preview => preview.contestStage !== "regional"),
    regional: visible.filter(preview => preview.contestStage === "regional").sort((a, b) => {
      const date = (previewContestDate(a) ?? "9999").localeCompare(previewContestDate(b) ?? "9999");
      const priority = preview => ({ ICPC: 0, CCPC: 1 })[previewOrganization(preview)] ?? 2;
      return date || priority(a) - priority(b) || a.id.localeCompare(b.id);
    }),
  };
}

function onlineRankValue(team) {
  return team.onlineRanks?.some(rank => rank !== null) ? team.onlineRanks : null;
}

export function previewPowerMetricIds(preview) {
  return preview.powerMetrics ?? [...preview.metricSources.map(source => source.id), "medals"];
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
    .map((team) => ({ id: team.id, value: valueOf(team), sourceIndex: team.sourceIndex, excluded: team.excluded }))
    .sort((left, right) => compare(left.value, right.value) || left.sourceIndex - right.sourceIndex);
  const counts = new Map();
  let groupStart = 0;
  let eligibleCount = 0;
  ordered.forEach((item, index) => {
    if (index && compare(item.value, ordered[index - 1].value)) groupStart = eligibleCount;
    counts.set(item.id, groupStart);
    if (!item.excluded) eligibleCount += 1;
  });
  return counts;
}

function competitionRanks(teams, valueOf, compare, skipNull = false) {
  const ordered = teams
    .filter((team) => !team.excluded)
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
    competitionRanks(teams, (team) => team.ratings[id] ?? null, comparePowerValues, true),
  ]));
  const medalRanks = competitionRanks(teams, (team) => team.medals, compareMedals);
  const onlineRanks = competitionRanks(teams, onlineRankValue, compareOnlineRanks, true);
  return new Map(teams.map((team) => [team.id, {
    ratings: Object.fromEntries(metricIds.map((id) => [id, ratingRanks.get(id).get(team.id)])),
    medals: medalRanks.get(team.id),
    ...(team.onlineRanks === undefined ? {} : { onlineRanks: onlineRanks.get(team.id) }),
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

export function buildPreviewPower(teams, metricIds = Object.keys(teams[0]?.ratings ?? {}), powerMetrics = [...metricIds, "medals"]) {
  const dimensions = powerMetrics.map(id => {
    if (id === "onlineRanks") return countStrictlyLower(teams, onlineRankValue, compareOnlineRanks);
    if (id === "medals") return countStrictlyLower(teams, team => team.medals, compareMedals);
    return countStrictlyLower(teams, team => previewRatingValue(id, team.ratings[id] ?? null), comparePowerValues);
  });
  const power = new Map(teams.map((team) => {
    const counts = dimensions.map((values) => values.get(team.id));
    return [team.id, { counts, vector: [...counts].sort((left, right) => right - left), rank: null }];
  }));
  const ranked = teams.filter((team) => !team.excluded).sort((left, right) => (
    comparePowerVectors(power.get(left.id).vector, power.get(right.id).vector)
    || left.sourceIndex - right.sourceIndex
  ));
  let previousVector = null;
  let rank = 0;
  ranked.forEach((team, index) => {
    const entry = power.get(team.id);
    if (previousVector === null || comparePowerVectors(entry.vector, previousVector)) rank = index + 1;
    const hasData = powerMetrics.some(id => id === "onlineRanks" ? onlineRankValue(team) !== null
      : id === "medals" ? ["gold", "silver", "bronze"].some(medal => team.medals[medal] > 0)
        : previewRatingValue(id, team.ratings[id] ?? null) !== null);
    entry.rank = hasData ? rank : null;
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
  return [...teams].sort((left, right) => (
    comparePreviewSortKeys(left, right, sort, order, power)
    || left.school.localeCompare(right.school, "zh-CN")
    || left.sourceIndex - right.sourceIndex
  ));
}

function comparePreviewSortKeys(left, right, sort, order, previewPower) {
  const direction = order === "asc" ? 1 : -1;
  if (sort === "school" || sort === "name") {
    return left[sort].localeCompare(right[sort], "zh-CN") * direction;
  }
  if (sort === "members") {
    return left.members.map(({ name }) => name).join("/").localeCompare(
      right.members.map(({ name }) => name).join("/"), "zh-CN",
    ) * direction;
  }
  if (sort === "onlineRanks") {
    const a = onlineRankValue(left), b = onlineRankValue(right);
    if (a === null && b === null) return 0;
    if (a === null) return 1;
    if (b === null) return -1;
    return compareOnlineRanks(a, b) * direction;
  }
  if (sort === "medals") return compareMedals(left.medals, right.medals) * direction;
  if (sort === "power") {
    return comparePowerVectors(
      previewPower.get(left.id).vector,
      previewPower.get(right.id).vector,
      order,
    );
  }
  return compareNullableNumber(
    left.ratings[sort] ?? null,
    right.ratings[sort] ?? null,
    order,
  );
}

export function buildPreviewSchoolRanks(sortedTeams, sort, previewPower = null) {
  if (["school", "name", "members"].includes(sort)) return new Map();
  const power = sort === "power" && !previewPower ? buildPreviewPower(sortedTeams) : previewPower;
  const rankedSchools = new Set();
  const ranks = new Map();
  let previousBest = null;
  let rank = 0;
  for (const team of sortedTeams) {
    if (team.excluded) continue;
    if (rankedSchools.has(team.school)) continue;
    rankedSchools.add(team.school);
    if (previousBest === null || comparePreviewSortKeys(team, previousBest, sort, "desc", power)) {
      rank = rankedSchools.size;
    }
    ranks.set(team.id, rank);
    previousBest = team;
  }
  return ranks;
}

export function readPreviewQuery(url) {
  const params = new URL(url, "http://localhost/").searchParams;
  return {
    previewSort: params.get("previewSort") || "power",
    previewOrder: params.get("previewOrder") === "asc" ? "asc" : "desc",
    previewContest: params.get("previewContest") || "",
    previewTeamType: ["official", "starred"].includes(params.get("previewTeamType"))
      ? params.get("previewTeamType") : "all",
  };
}

export function writePreviewQuery(url, query) {
  const next = new URL(url, "http://localhost/");
  if (query.view !== "preview") {
    for (const key of ["previewSort", "previewOrder", "previewContest", "previewTeamType", "achievement"]) next.searchParams.delete(key);
    return next;
  }
  next.searchParams.set("view", "preview");
  if (query.contest) next.searchParams.set("previewContest", query.contest);
  else next.searchParams.delete("previewContest");
  if (query.sort && query.sort !== "power") next.searchParams.set("previewSort", query.sort);
  else next.searchParams.delete("previewSort");
  if (query.order === "asc") next.searchParams.set("previewOrder", "asc");
  else next.searchParams.delete("previewOrder");
  next.searchParams.delete("achievement");
  if (["official", "starred"].includes(query.teamType)) next.searchParams.set("previewTeamType", query.teamType);
  else next.searchParams.delete("previewTeamType");
  return next;
}

export function createPreviewStore(indexUrl, fetchImpl = globalThis.fetch) {
  return {
    async getRegionalCutoffs(entry) {
      if (!entry.regionalCutoffsPath) return [];
      const document = await fetchJson(resolveDataUrl(entry.regionalCutoffsPath, indexUrl), fetchImpl);
      return validateRegionalCutoffs(document, entry.id).contests;
    },
    async getPreviews(entry) {
      const entries = entry.previews ?? (entry.previewPath ? [{ path: entry.previewPath }] : []);
      if (!entries.length) throw new Error(`Series has no preview data: ${entry.id}`);
      const previews = await Promise.all(entries.map(async item => {
        const preview = validatePreview(await fetchJson(resolveDataUrl(item.path, indexUrl), fetchImpl));
        if (preview.seriesId !== entry.id) fail("preview.seriesId", `expected ${entry.id}, received ${preview.seriesId}`);
        if (item.id && preview.id !== item.id) fail("preview.id", `expected ${item.id}`);
        return preview;
      }));
      if (new Set(previews.map(p => p.id)).size !== previews.length) fail("preview.id", "duplicate contest ID");
      return previews;
    },
    async getSeries(entry) {
      return (await this.getPreviews(entry))[0];
    },
  };
}

export function validateRegionalCutoffs(document, seriesId) {
  object(document, "regionalCutoffs");
  if (document.schemaVersion !== 1 || document.seriesId !== seriesId) fail("regionalCutoffs", "invalid schema or series");
  array(document.contests, "regionalCutoffs.contests");
  const ids = new Set();
  for (const contest of document.contests) {
    const path = "regionalCutoffs.contest";
    object(contest, path);
    for (const key of ["id", "title", "hostSchool", "sortAt"]) string(contest[key], `${path}.${key}`);
    if (!Number.isFinite(Date.parse(contest.sortAt))) fail(path, "invalid sortAt");
    if (contest.contestStage !== "regional") fail(path, "expected regional stage");
    if (ids.has(contest.id)) fail(path, "duplicate contest ID");
    ids.add(contest.id);
    object(contest.cutoffs, `${path}.cutoffs`);
    for (const key of ["cup", "gold", "silver", "bronze"]) {
      if (contest.cutoffs[key] !== null) integer(contest.cutoffs[key], `${path}.cutoffs.${key}`, 1);
    }
    for (const key of ["teamCount", "officialTeamCount", "excludedTeamCount", "matchedOfficialTeamCount"]) {
      integer(contest[key], `${path}.${key}`, 0);
    }
    if (contest.officialTeamCount + contest.excludedTeamCount !== contest.teamCount
      || contest.matchedOfficialTeamCount > contest.officialTeamCount) fail(path, "inconsistent team counts");
  }
  return document;
}
