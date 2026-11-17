// CCPCF awards school slots by best regional rank, independently of ICPC traversal.
import { validateQualification } from "./qualification.mjs?v=20261117-104";

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

export function buildCcpcfQualification(data) {
  validateQualification(data);
  if (data.kind !== "ccpcf") throw new TypeError("qualification.kind: expected ccpcf");
  // Date order is for presentation only; station size never changes qualification.
  const stations = data.stations.toSorted((a, b) => compareText(a.date, b.date) || compareText(a.id, b.id))
    .map(s => ({ ...s, entries: s.teams.filter(t => t.rank > 0) }));
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
    if (representative.team.rank === 0) continue;
    const group = { key: appearances.map(a => a.team.key).sort(compareText)[0],
      schoolKey: representative.team.schoolKey, bestRank: representative.team.rank,
      complete: appearances.every(a => a.team.identityComplete), appearances, representative };
    if (!schools.has(group.schoolKey)) schools.set(group.schoolKey, []);
    schools.get(group.schoolKey).push(group);
  }
  for (const groups of schools.values()) groups.sort(compareGroup);
  const pendingCount = stations.filter(s => s.status === "pending").length;
  const channels = [data.firstQuota, data.secondQuota].map((quota, index) => {
    const entries = [...schools.values()].filter(groups => groups.length > index).map(groups => groups[index]).sort(compareGroup);
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
      if (group.selected) selected.push(group);
    });
    const cutoffRank = selected.at(-1)?.bestRank ?? null;
    const regionRows = stations.map(station => cutoffRank === null ? 0 : station.status === "pending"
      ? cutoffRank : station.entries.filter(team => team.rank <= cutoffRank).length);
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
            + (group.certainty === "safe" ? "在未知赛站严格更好名次的上界下仍可保留。" : "后续成绩、成员合并或身份核验仍可能影响名额。")
          : index >= 2 ? "合并后本校已有两支排名更好的队伍。" : "当前未达到本渠道名额线。";
        cells.set(position, { team, row, column, position, role, certainty: selected ? group.certainty : null,
          pressure: selected ? group.pressure : null, hosting: null, schoolRank: index + 1,
          channelRank: group.channelRank ?? null, bestRank: group.bestRank, mergedKey: group.key, reason,
          searchText: group.appearances.flatMap(a => [a.team.name, ...a.team.members]).join(" ") });
      }
    }
  }
  return { mode: "ccpcf", stations, channels, schools, cells, current, safe, pendingCount,
    maxRows: Math.max(...stations.map(s => s.entries.length), boundaryRow, 1), boundaryRow, hongkong: null };
}
