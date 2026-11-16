// Pure qualification calculations. Unknown results are never filled with predicted teams.
import { fetchJson, resolveDataUrl } from "./data.mjs?v=20261116-95";

const check = (condition, path, message) => {
  if (!condition) throw new TypeError(`${path}: ${message}`);
};
const nonempty = value => typeof value === "string" && value.length > 0;
const integer = (value, min = 0) => Number.isSafeInteger(value) && value >= min;

export function validateQualification(data) {
  check(data?.schemaVersion === 1, "qualification.schemaVersion", "unsupported version");
  check(nonempty(data.seriesId) && /^\d{4}-\d{2}-\d{2}$/.test(data.asOf), "qualification", "invalid series/date");
  check(data.disclaimer === "民间数据，仅供参考，不代表官方结果", "qualification.disclaimer", "required notice");
  check(integer(data.ecfMainlandQuota, 1) && integer(data.ecfSchoolCap, 1), "qualification", "invalid quota");
  check(Array.isArray(data.rules) && data.rules.length >= 2, "qualification.rules", "missing rules");
  check(data.rules.every(rule => nonempty(rule.title) && /^https:\/\//.test(rule.url)), "qualification.rules", "invalid rule source");
  check(Array.isArray(data.stations) && data.stations.length > 0, "qualification.stations", "empty stations");
  const ids = new Set();
  for (const [index, station] of data.stations.entries()) {
    const path = `qualification.stations[${index}]`;
    check(nonempty(station.id) && !ids.has(station.id), path, "duplicate/missing station ID");
    ids.add(station.id);
    check(nonempty(station.title) && !Number.isNaN(Date.parse(station.date)), path, "invalid title/date");
    check(["mainland", "hongkong"].includes(station.region), path, "invalid region");
    check(["finished", "pending"].includes(station.status), path, "invalid status");
    check(Array.isArray(station.teams), path, "missing teams");
    check(nonempty(station.source?.title) && /^https:\/\//.test(station.source?.url), path, "missing source");
    if (station.hostSchool !== undefined || station.hostSource !== undefined) {
      check(nonempty(station.hostSchool) && /^https:\/\//.test(station.hostSource), path, "invalid host school/source");
    }
    if (station.status === "pending") {
      check(integer(station.estimatedCount, 1) && station.teams.length === 0, path, "pending requires estimate and no results");
      continue;
    }
    check(integer(station.officialCount) && station.officialCount === station.teams.length, path, "official count mismatch");
    const keys = new Set();
    let lastRank = 0;
    for (const team of station.teams) {
      check(nonempty(team.key) && !keys.has(team.key), path, "duplicate/missing team key");
      keys.add(team.key);
      check([team.schoolKey, team.school, team.name].every(nonempty), path, "missing team identity");
      check(Array.isArray(team.members) && team.members.length >= 1 && team.members.length <= 3 && team.members.every(nonempty), path, "invalid members");
      check(typeof team.identityComplete === "boolean" && team.identityComplete === (team.members.length === 3), path, "invalid identity completeness");
      check(integer(team.rank, 1) && team.rank >= lastRank && integer(team.solved), path, "invalid/unsorted result");
      lastRank = team.rank;
    }
    check(station.effectiveCount === station.teams.filter(t => t.solved > 0).length, path, "effective count mismatch");
  }
  return data;
}

export async function loadQualification(entry, indexUrl) {
  const data = validateQualification(await fetchJson(resolveDataUrl(entry.qualificationPath, indexUrl)));
  check(data.seriesId === entry.id, "qualification.seriesId", "series mismatch");
  return data;
}

export function stationSize(station) {
  return station.status === "finished" ? station.effectiveCount : station.estimatedCount;
}

export function orderedStations(data, mode) {
  return data.stations.filter(s => mode === "wf" || s.region === "mainland")
    .toSorted((a, b) => stationSize(b) - stationSize(a) || a.date.localeCompare(b.date) || a.id.localeCompare(b.id))
    .map(station => {
      const seen = new Set();
      const entries = station.teams.filter(team => {
        if (!team.solved) return false;
        if (mode === "ecf") return true;
        if (seen.has(team.schoolKey)) return false;
        seen.add(team.schoolKey);
        return true;
      });
      return { ...station, entries };
    });
}

// All pending cells in the pessimistic run take a new slot (distinct school/team).
// This yields a conservative school-quota bound, not a forecast of future results.
export function scanQualification(stations, mode, quota, cap, reservePending = false) {
  const selected = new Map();
  const schools = new Map();
  const visited = new Map();
  let used = 0;
  let pendingBefore = 0;
  let frontier = -1;
  const maxRows = Math.max(...stations.map(s => s.status === "pending" ? stationSize(s) : s.entries.length));
  for (let row = 0; row < maxRows && used < quota; row++) {
    for (let column = 0; column < stations.length && used < quota; column++) {
      const station = stations[column];
      const position = row * stations.length + column;
      frontier = position;
      if (station.status === "pending") {
        if (row < stationSize(station)) {
          pendingBefore++;
          if (reservePending) used++;
        }
        continue;
      }
      const team = station.entries[row];
      if (!team) continue;
      const key = mode === "wf" ? team.schoolKey : team.key;
      const reason = selected.has(key) ? "duplicate" : (schools.get(team.schoolKey) ?? 0) >= cap ? "cap" : "selected";
      visited.set(position, { reason, pendingBefore });
      if (reason !== "selected") continue;
      used++;
      selected.set(key, { team, position, row, column, order: used, pendingBefore });
      schools.set(team.schoolKey, (schools.get(team.schoolKey) ?? 0) + 1);
    }
  }
  return { selected, schools, visited, frontier, used, reserved: used - selected.size };
}

export function buildQualification(data, mode) {
  check(["wf", "ecf"].includes(mode), "mode", "expected wf or ecf");
  validateQualification(data);
  const stations = orderedStations(data, mode);
  const quota = mode === "wf" ? data.stations.length : data.ecfMainlandQuota;
  const cap = mode === "wf" ? 1 : data.ecfSchoolCap;
  const current = scanQualification(stations, mode, quota, cap);
  const conservative = scanQualification(stations, mode, quota, cap, true);
  const pendingCount = stations.filter(s => s.status === "pending").length;
  const safe = new Set();
  const cells = new Map();
  // Known teams keep relative traversal order. Future teams may take a school's
  // remaining slots; an ECF team is certain only if even that cannot fill its cap.
  const earlierSchoolTeams = new Map();
  const maxRows = Math.max(...stations.map(s => s.entries.length), 1);
  let unknownBefore = 0;
  for (let row = 0; row < maxRows; row++) {
    for (let column = 0; column < stations.length; column++) {
      const station = stations[column];
      const position = row * stations.length + column;
      if (station.status === "pending") {
        if (row < stationSize(station)) unknownBefore++;
        continue;
      }
      const team = station.entries[row];
      if (!team) continue;
      const key = mode === "wf" ? team.schoolKey : team.key;
      const selected = current.selected.get(key);
      const hostStations = mode === "wf" ? stations.filter(s => s.hostSchool === team.schoolKey) : [];
      // Record only the ordinary regional performance threshold, not C-slot eligibility.
      // A school's own host station cannot supply the qualifying performance.
      const hosting = row < 10 && hostStations.length && !hostStations.some(s => s.id === station.id)
        ? { schoolRank: row + 1, stations: hostStations.map(s => s.title) } : null;
      const schoolTeams = earlierSchoolTeams.get(team.schoolKey) ?? new Set();
      const atOwnPosition = selected?.position === position;
      let role = "outside";
      let reason = "当前成绩尚未进入此渠道的出线区域，后续比赛仍可能改变结果。";
      let certainty = null;
      let pressure = null;
      if (selected) {
        if (atOwnPosition) {
          role = "selected";
          const quotaSafe = conservative.selected.has(key);
          const capSafe = mode === "wf" || schoolTeams.size + unknownBefore < cap;
          const identitySafe = mode === "wf" || team.identityComplete;
          certainty = quotaSafe && capSafe && identitySafe ? "safe" : "risk";
          pressure = {
            level: quota - selected.order >= selected.pendingBefore ? "low"
              : (quota - selected.order + 1) / selected.pendingBefore > 0.5 ? "medium" : "high",
            slotTolerance: quota - selected.order,
            pendingBefore: selected.pendingBefore,
            schoolTolerance: mode === "ecf" ? Math.max(0, cap - 1 - schoolTeams.size) : null,
            schoolRisk: !capSafe,
          };
          if (certainty === "safe") safe.add(key);
          reason = certainty === "safe"
            ? mode === "wf" ? "按当前规模估计，即使未赛站逐行新增高校占位，本校仍获区域赛名额；参赛队由学校从候选队中选择。" : "按当前规模估计，未赛站新增占位和同校队伍上限均不会挤掉该队。"
            : !identitySafe ? "成员资料不完整，跨站身份需核实，暂不标记确定。"
              : !capSafe ? "当前处于出线区域，但后续同校其他队伍可能先达到每校上限，具体队伍尚未锁定。"
                : "当前处于出线区域；未赛站新增名额占位后可能跌出。";
        } else if (mode === "wf" && position <= current.frontier && team.key !== selected.team.key) {
          role = "candidate";
          certainty = safe.has(key) ? "safe" : "risk";
          reason = "本校在当前出线区域内的另一支候选队，学校只能选一队；候选范围随后续结果变化。";
        } else {
          role = "duplicate";
          reason = mode === "wf" ? "本校已在更早位置计入；该行未新增高校名额。" : "相同学校及三名成员的队伍已在更早赛站计入，不重复占名额。";
        }
      } else if (current.visited.get(position)?.reason === "cap") {
        role = "duplicate";
        reason = "本校在当前成绩推演中已达到 3 支队伍的成绩渠道上限。";
      }
      cells.set(position, { team, role, certainty, reason, pressure, hosting, row, column, position, order: atOwnPosition ? selected.order : null });
      schoolTeams.add(team.key);
      earlierSchoolTeams.set(team.schoolKey, schoolTeams);
    }
  }
  // Equal ranks at a frontier have no official tie-break in the archived rules.
  for (const [key, selected] of current.selected) {
    const entries = stations[selected.column].entries;
    if (entries.some((team, row) => row !== selected.row && team.rank === selected.team.rank)) {
      const cell = cells.get(selected.position);
      cell.certainty = "risk";
      cell.reason += " 同成绩并列的处理需以组委会为准。";
      safe.delete(key);
    }
  }
  for (const cell of cells.values()) {
    if (cell.role === "candidate") cell.certainty = safe.has(cell.team.schoolKey) ? "safe" : "risk";
  }
  return { mode, stations, quota, cap, current, conservative, cells, safe, pendingCount, maxRows,
    boundaryRow: Math.floor(current.frontier / stations.length) + 1 };
}

// Edges of the row-major prefix, including its stepped final row.
export function qualificationRegionEdges(position, columns, frontier) {
  if (position < 0 || position > frontier) return [];
  const edges = [];
  if (position < columns) edges.push("top");
  if (position % columns === 0) edges.push("left");
  if (position % columns === columns - 1 || position === frontier) edges.push("right");
  if (position + columns > frontier) edges.push("bottom");
  return edges;
}

export function cellPresentation(cell) {
  if (cell.role === "candidate") return { className: "candidate", label: "可选队伍", detail: cell.certainty === "safe" ? "本校确定有名额" : "本校名额仍待定" };
  if (cell.role === "selected") return cell.certainty === "safe"
    ? { className: "safe", label: "确定有名额", detail: "当前出线位置" }
    : { className: `pressure-${cell.pressure?.level ?? "low"}`, label: "当前出线 待定", detail: "具体名额尚未锁定" };
  return cell.role === "duplicate"
    ? { className: "duplicate", label: "重复 / 达上限", detail: "不新增名额" }
    : { className: "outside", label: "当前未出线", detail: "" };
}
