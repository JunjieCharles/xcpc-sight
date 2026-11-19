// CCPCF awards school slots by best regional rank, independently of ICPC traversal.
import { validateQualification } from "./qualification.mjs?v=20261119-112";
import { buildPreviewPower, buildPreviewRanks, previewPowerDimensions, previewPowerMetricIds, sortPreviewTeams } from "./preview.mjs?v=20261119-112";

const compareText = (a, b) => a < b ? -1 : a > b ? 1 : 0;
const compareGroup = (a, b) => a.bestRank - b.bestRank || compareText(a.key, b.key);

// Outline a rank prefix in each station, including ties and pending rank slots.
export function ccpcfRegionEdges(row, column, regionRows) {
  if (row < 0 || column < 0 || column >= regionRows.length || row >= regionRows[column]) return [];
  const edges = [];
  if (row === 0) edges.push("top");
  if (column === 0 || row >= regionRows[column - 1]) edges.push("left");
  if (column === regionRows.length - 1 || row >= regionRows[column + 1]) edges.push("right");
  if (row === regionRows[column] - 1) edges.push("bottom");
  return edges;
}

function groupSchools(stations) {
  // Unranked records can still connect rosters, but never supply a best rank.
  const records = stations.flatMap((station, column) => station.teams.map(team => ({ team, row: station.entries.indexOf(team), column })));
  const parents = records.map((_, i) => i);
  const root = i => {
    while (parents[i] !== i) { parents[i] = parents[parents[i]]; i = parents[i]; }
    return i;
  };
  const members = new Map();
  records.forEach(({ team }, i) => {
    for (const member of team.memberKeys) {
      const key = JSON.stringify([team.schoolKey, member]);
      if (members.has(key)) parents[root(i)] = root(members.get(key));
      else members.set(key, i);
    }
  });
  const components = new Map();
  records.forEach((record, i) => {
    const key = root(i);
    if (!components.has(key)) components.set(key, []);
    components.get(key).push(record);
  });
  const schools = new Map();
  for (const appearances of components.values()) {
    appearances.sort((a, b) => (a.team.rank || Infinity) - (b.team.rank || Infinity) || a.column - b.column || compareText(a.team.key, b.team.key));
    const representative = appearances[0];
    const forecastCount = appearances.filter(a => a.team.forecast).length;
    if (!representative.team.rank && !forecastCount) continue;
    const historical = appearances.find(a => !a.team.forecast && a.team.rank > 0);
    const group = { key: appearances.map(a => a.team.key).sort(compareText)[0],
      schoolKey: representative.team.schoolKey, bestRank: representative.team.rank || Infinity,
      historicalRank: historical?.team.rank ?? Infinity, historicalKey: historical?.team.key, forecastCount,
      complete: appearances.every(a => a.team.identityComplete), appearances, representative };
    if (!schools.has(group.schoolKey)) schools.set(group.schoolKey, []);
    schools.get(group.schoolKey).push(group);
  }
  for (const groups of schools.values()) groups.sort(compareGroup);
  return schools;
}

function channelEntries(schools, index) {
  return [...schools.values()].map(groups => groups[index])
    .filter(group => group && Number.isFinite(group.bestRank)).sort(compareGroup);
}

function forecastTeams(station, preview, metric) {
  const metricIds = preview.metricSources.map(s => s.id);
  const power = metric === "power" ? buildPreviewPower(preview.teams, metricIds, previewPowerMetricIds(preview)) : null;
  const ranks = power ? null : buildPreviewRanks(preview.teams, metricIds);
  const official = sortPreviewTeams(preview.teams.filter(t => !t.excluded), metric, "desc", power);
  const identities = station.previewIdentities;
  if (!identities || Object.keys(identities).length !== official.length) throw new Error(`${station.id}: 前瞻身份名单不匹配`);
  return official.map(team => {
    const identity = identities[team.id];
    const members = team.members.map(m => m.name);
    if (!identity?.schoolKey || !Array.isArray(identity.memberKeys) || identity.memberKeys.length !== members.length
      || !identity.memberKeys.every(k => typeof k === "string" && k.length) || new Set(identity.memberKeys).size !== members.length) {
      throw new Error(`${station.id}/${team.id}: 缺少有效的前瞻选手身份`);
    }
    const row = ranks?.get(team.id);
    const rank = power ? power.get(team.id).rank : row.ratings[metric] ?? row[metric] ?? null;
    return { key: team.id, school: team.school, name: team.name, members, ...identity,
      identityComplete: members.length === 3, rank, forecast: true };
  });
}

// At most r-1 results can beat r. Each rival school needs 0, 1 or 2 distinct
// Xiamen components in those places. Spending them on the cheapest rivals first
// attains the worst case: schools are disjoint and boundary ties keep their slot.
function guaranteedChannel(schools, school, number, quota, rank, places) {
  const costs = [0, 0, 0];
  for (const [rival, groups] of schools) {
    if (rival === school) continue;
    const need = Math.max(0, number - groups.filter(g => g.historicalRank < rank).length);
    if (groups.filter(g => g.forecastCount && g.historicalRank >= rank).length >= need) costs[need]++;
  }
  const singles = Math.min(places, costs[1]);
  const doubles = Math.min(Math.floor((places - singles) / 2), costs[2]);
  return costs[0] + singles + doubles < quota;
}

// For a fixed best rank, find how many places strictly before it must be spent
// on home teams to put the target in a given channel. At most one extra home
// group is needed for channel 2. Infinity means this channel is unreachable.
function homePlaces(extra, contenders, canTie, fillers, places, improved) {
  if (extra < 0 || extra > contenders.length) return Infinity;
  if (!extra) return improved && fillers < places ? Infinity : 0;
  if (canTie && fillers >= places) return 0;
  if (places === 0) return Infinity;
  return !improved || contenders.some(g => fillers + g.forecastCount >= places) ? 1 : Infinity;
}

function guaranteedTeam(schools, target, teamCount, quotas) {
  const peers = schools.get(target.schoolKey).filter(g => g !== target);
  const awayCount = teamCount - target.forecastCount - peers.reduce((sum, g) => sum + g.forecastCount, 0);
  // An improvement can move a team from channel 2 to channel 1; neither
  // channel's national cutoff is assumed to dominate the other's.
  const ranks = [target.historicalRank];
  if (target.forecastCount) {
    for (let r = 1; r < target.historicalRank && r <= teamCount; r++) ranks.push(r);
  }
  for (const rank of ranks) {
    const improved = rank < target.historicalRank;
    const ahead = peers.filter(g => g.historicalRank < rank || (g.historicalRank === rank && g.key < target.key));
    const contenders = peers.filter(g => g.forecastCount && !ahead.includes(g));
    const places = rank - 1;
    // The target's historical rank can be matched by one Xiamen finisher.
    // If the target itself supplies that rank, the Xiamen place is occupied.
    const canTie = !improved && rank <= teamCount && contenders.some(g => g.key < target.key);
    if (ahead.length + Math.min(contenders.length, places + Number(canTie)) >= 2) return false;
    const fillers = awayCount + ahead.reduce((sum, g) => sum + g.forecastCount, 0);
    for (const [index, quota] of quotas.entries()) {
      const cost = homePlaces(index - ahead.length, contenders, canTie, fillers, places, improved);
      if (cost <= places && !guaranteedChannel(schools, target.schoolKey, index + 1, quota, rank, places - cost)) return false;
    }
  }
  return true;
}

export function buildCcpcfQualification(data, previews = null, metric = "power") {
  validateQualification(data);
  if (data.kind !== "ccpcf") throw new TypeError("qualification.kind: expected ccpcf");
  const stations = data.stations.toSorted((a, b) => compareText(a.date, b.date) || compareText(a.id, b.id))
    .map(s => ({ ...s, entries: s.teams.filter(t => t.rank > 0) }));
  const schools = groupSchools(stations);
  const pendingCount = stations.filter(s => s.status === "pending").length;
  const forecasts = new Map();
  if (previews) for (const station of stations.filter(s => s.status === "pending" && s.previewId)) {
    const preview = previews.find(p => p.id === station.previewId);
    if (!preview) throw new Error(`${station.id}: 找不到前瞻 ${station.previewId}`);
    forecasts.set(station, preview);
  }
  const dimensions = [...forecasts.values()].map(previewPowerDimensions);
  const forecastMetrics = dimensions.length ? [{ id: "power", title: "综合战力" },
    ...dimensions[0].filter(({ id }) => dimensions.every(options => options.some(option => option.id === id)))] : [];
  const forecastMetric = forecastMetrics.find(option => option.id === metric);
  for (const [station, preview] of forecasts) {
    if (!forecastMetric) throw new RangeError(`未知的前瞻排名指标：${metric}`);
    station.entries = forecastTeams(station, preview, metric);
  }
  const projection = forecasts.size && forecasts.size === pendingCount
    ? groupSchools(stations.map(s => forecasts.has(s) ? { ...s, teams: s.entries } : s)) : null;
  const lastStation = pendingCount === 1 ? [...forecasts.keys()][0] : null;
  const forecastSlots = new Map();
  const quotas = [data.firstQuota, data.secondQuota];
  const projectedQualifiers = new Map();
  if (projection) quotas.forEach((quota, index) => {
    const projectedEntries = channelEntries(projection, index);
    const forecastCutoff = projectedEntries[quota - 1]?.bestRank ?? Infinity;
    for (const group of projectedEntries) {
      if (group.bestRank > forecastCutoff) break;
      if (group.historicalKey) projectedQualifiers.set(group.historicalKey, group);
      const { team } = group.representative;
      if (team.forecast) forecastSlots.set(team, index + 1);
    }
  });
  const channels = quotas.map((quota, index) => {
    const entries = channelEntries(schools, index);
    const selected = [];
    let rank = 0;
    entries.forEach((group, i) => {
      // Competition rank: 1, 1, 3. All ties at the threshold receive school slots.
      if (i === 0 || group.bestRank !== entries[i - 1].bestRank) rank = i + 1;
      group.channel = index + 1;
      group.channelRank = rank;
      group.selected = rank <= quota;
      // A future station has at most r-1 teams strictly better than rank r.
      // Existing schools may improve, so treating all those teams as extra
      // competitors also bounds that case. Equal ranks cannot displace a tie.
      const unknown = pendingCount * (group.bestRank - 1);
      const tolerance = quota - rank;
      const identitySafe = index === 0 || schools.get(group.schoolKey).every(g => g.complete);
      // A future roster can bridge two known components. Until all nationals
      // finish we cannot guarantee the school's second independent team.
      const mergeSafe = index === 0 || pendingCount === 0;
      group.certainty = rank + unknown <= quota && identitySafe && mergeSafe ? "safe" : "risk";
      group.pressure = { level: tolerance >= unknown ? "low" : (tolerance + 1) / unknown > 0.5 ? "medium" : "high",
        slotTolerance: tolerance, pendingBefore: unknown, schoolRisk: !mergeSafe || !identitySafe };
      if (lastStation && group.selected) {
        const projected = projectedQualifiers.get(group.representative.team.key);
        const safe = projected && guaranteedTeam(projection, projected, lastStation.entries.length, quotas);
        group.outlook = !projected ? "displaced" : safe ? "safe" : "uncertain";
        group.certainty = safe ? "safe" : "risk";
        group.pressure = null;
      }
      if (group.selected) selected.push(group);
    });
    const cutoffRank = selected.at(-1)?.bestRank ?? null;
    const regionRows = stations.map(station => cutoffRank === null ? 0 : station.status === "pending" && !station.entries.length
      ? cutoffRank : station.entries.filter(team => team.rank > 0 && team.rank <= cutoffRank).length);
    return { number: index + 1, quota, entries, selected, cutoffRank, regionRows };
  });
  const current = { selected: new Map(), frontier: -1 };
  const safe = new Set();
  const cells = new Map();
  let boundaryRow = Math.max(0, ...channels.flatMap(channel => channel.regionRows));
  for (const groups of schools.values()) {
    for (const [index, group] of groups.entries()) {
      const selected = Boolean(group.selected);
      if (selected) {
        current.selected.set(group.key, group);
        if (group.certainty === "safe") safe.add(group.key);
      }
      for (const appearance of group.appearances) {
        const { row, column, team } = appearance;
        if (row < 0) continue;
        const position = row * stations.length + column;
        const representative = appearance === group.representative;
        const role = selected ? representative ? "selected" : "duplicate" : "outside";
        if (role === "selected") boundaryRow = Math.max(boundaryRow, row + 1);
        const reason = selected
          ? `本校第 ${group.channel} 名额渠道第 ${group.channelRank} 名（最佳站内排名 ${group.bestRank}）；名额归学校。`
            + (group.outlook ? ccpcfOutlooks[group.outlook].legend : group.certainty === "safe" ? "在未知赛站严格更好名次的上界下仍可保留。" : "后续成绩、成员合并或身份核验仍可能影响名额。")
          : index >= 2 ? "合并后本校已有两支排名更好的队伍。" : "当前未达到本渠道名额线。";
        cells.set(position, { team, row, column, position, role, certainty: selected ? group.certainty : null,
          outlook: role === "selected" ? group.outlook : null,
          pressure: selected ? group.pressure : null, hosting: null, schoolRank: index + 1,
          channelRank: group.channelRank ?? null, bestRank: group.bestRank, mergedKey: group.key, reason,
          searchText: group.appearances.flatMap(a => [a.team.name, ...a.team.members]).join(" ") });
      }
    }
  }
  for (const [column, station] of stations.entries()) {
    if (!forecasts.has(station)) continue;
    station.entries.forEach((team, row) => {
      cells.set(row * stations.length + column, { team, role: "forecast",
        forecastSlot: forecastSlots.get(team) ?? null, reason: `${station.title}站正式队赛前排名（${forecastMetric.title}）` });
    });
  }
  return { mode: "ccpcf", stations, channels, schools, cells, current, safe, pendingCount, forecastMetrics, hasForecast: Boolean(projection),
    maxRows: Math.max(...stations.map(s => s.entries.length), boundaryRow, 1), boundaryRow, hongkong: null };
}

export const ccpcfOutlooks = {
  displaced: { legend: "按前瞻本队将被挤出", badge: "待定出线" },
  safe: { legend: "任意顺序本队均出线", badge: "确定出线" },
  uncertain: { legend: "按前瞻本队出线，仍有风险", badge: "待定出线" },
};
