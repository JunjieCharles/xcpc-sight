import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

test("both boards use one pending label with pressure colors and distinct guaranteed places", () => {
  for (const level of ["low", "medium", "high"]) {
    const cell = { role: "selected", certainty: "risk", pressure: { level } };
    assert.deepEqual(cellPresentation(cell), {
      className: `pressure-${level}`, label: "待定出线", detail: "具体名额尚未锁定",
    });
    assert.equal(cell.certainty, "risk");
    assert.equal(cellPresentation({ ...cell, certainty: "safe" }).label, "确定出线");
  }
  for (const role of ["duplicate", "outside"]) {
    assert.equal(cellPresentation({ role }).className, role);
  }
});
import { buildQualification, scanQualification, orderedStations, validateQualification, cellPresentation, qualificationRegionEdges } from "../static/js/qualification.mjs";

test("qualification outline follows the prefix perimeter including a stepped last row", () => {
  assert.deepEqual(qualificationRegionEdges(0, 4, 0), ["top", "left", "right", "bottom"]);
  assert.deepEqual(qualificationRegionEdges(0, 4, 5), ["top", "left"]);
  assert.deepEqual(qualificationRegionEdges(1, 4, 5), ["top"]);
  assert.deepEqual(qualificationRegionEdges(2, 4, 5), ["top", "bottom"]);
  assert.deepEqual(qualificationRegionEdges(3, 4, 5), ["top", "right", "bottom"]);
  assert.deepEqual(qualificationRegionEdges(4, 4, 5), ["left", "bottom"]);
  assert.deepEqual(qualificationRegionEdges(5, 4, 5), ["right", "bottom"]);
  assert.deepEqual(qualificationRegionEdges(6, 4, 5), []);
  assert.deepEqual(qualificationRegionEdges(3, 4, 7), ["top", "right"]);
  assert.deepEqual(qualificationRegionEdges(7, 4, 7), ["right", "bottom"]);
  assert.deepEqual(qualificationRegionEdges(0, 4, -1), []);
});

const source = { title: "fixture", url: "https://example.org/rules" };
function team(school, number = 1, rank = 1, solved = 1) {
  return { key: `${school}-${number}`, schoolKey: school, school, name: `${school} team ${number}`,
    members: [`${school}${number}a`, `${school}${number}b`, `${school}${number}c`], identityComplete: true, rank, solved };
}
function station(id, teams, options = {}) {
  return { id, title: id, date: "2026-11-01", region: "mainland", status: "finished",
    officialCount: teams.length, effectiveCount: teams.filter(t => t.solved > 0).length, teams, source, ...options };
}
function data(stations, extra = {}) {
  return { schemaVersion: 1, seriesId: "test", asOf: "2026-11-16", disclaimer: "民间数据，仅供参考，不代表官方结果",
    ecfMainlandQuota: 3, ecfSchoolCap: 3, rules: [source, source], stations, ...extra };
}
const pending = (id, n = 2) => station(id, [], { status: "pending", estimatedCount: n });

test("hosting marks use other-station school top ten without allocating C slots", () => {
  const teams = [team("First", 1, 1), team("First", 2, 2),
    ...Array.from({ length: 8 }, (_, i) => team(`Other${i}`, 1, i + 3)),
    team("Host10", 1, 20), team("Host11", 1, 21)];
  const hostMetadata = school => ({ hostSchool: school, hostSource: "https://example.org/invitation" });
  const d = data([station("away", teams),
    station("own", [team("Host10")], hostMetadata("Host10")),
    { ...pending("future"), ...hostMetadata("Host11") }]);
  const plain = structuredClone(d);
  plain.stations.forEach(s => { delete s.hostSchool; delete s.hostSource; });
  const model = buildQualification(d, "wf");
  const marked = [...model.cells.values()].filter(c => c.hosting);
  assert.equal(marked.length, 1);
  assert.equal(marked[0].team.schoolKey, "Host10");
  assert.equal(marked[0].team.rank, 20, "threshold uses school rank, not raw team rank");
  assert.deepEqual(marked[0].hosting, { schoolRank: 10, stations: ["own"] });
  assert.deepEqual(model.current, buildQualification(plain, "wf").current);
  assert.deepEqual(model.safe, buildQualification(plain, "wf").safe);
  assert.ok([...buildQualification(d, "ecf").cells.values()].every(c => c.hosting === null));
  d.stations[2].hostSchool = "First";
  assert.ok([...buildQualification(d, "wf").cells.values()].some(c => c.hosting?.stations.includes("future")), "pending hosts count");
  d.stations[2].hostSource = "";
  assert.throws(() => validateQualification(d), /host school\/source/);
});

test("published host metadata marks only Wuhan University's Shenyang school rank seven", () => {
  const snapshot = JSON.parse(fs.readFileSync(new URL("../static/data/qualification/2026-2027.json", import.meta.url)));
  const model = buildQualification(snapshot, "wf");
  const marked = [...model.cells.values()].filter(c => c.hosting);
  assert.deepEqual(marked.map(c => [c.team.schoolKey, model.stations[c.column].title, c.hosting.schoolRank]), [["武汉大学", "沈阳", 7]]);
});

test("station order uses scored formal counts and estimates, with date tie-break", () => {
  const d = data([station("large-roster", [team("A"), team("B", 1, 2, 0), team("C", 1, 3, 0)]),
    station("earlier", [team("D"), team("E", 1, 2)], { date: "2026-10-01" }), pending("future", 2)]);
  assert.deepEqual(orderedStations(d, "wf").map(s => s.id), ["earlier", "future", "large-roster"]);
  assert.equal(orderedStations(d, "ecf").at(-1).entries.length, 1);
});

test("WF traverses school rows, not raw ranks, and exposes alternative teams only inside frontier", () => {
  const d = data([station("one", [team("A"), team("A", 2, 2), team("B", 1, 3)]),
    station("two", [team("A", 3), team("C", 1, 2)])]);
  const m = buildQualification(d, "wf");
  assert.deepEqual([...m.current.selected.keys()], ["A", "B"]);
  assert.equal(m.cells.get(1).role, "candidate");
  assert.equal(m.cells.get(3).role, "outside");
  assert.equal(cellPresentation(m.cells.get(1)).label, "可选队伍");
});

test("ECF deduplicates roster across stations, limits schools to three, excludes HK", () => {
  const d = data([station("one", [team("A"), team("A", 2, 2), team("A", 3, 3), team("A", 4, 4), team("B", 1, 5)]),
    station("two", [team("A"), team("C", 1, 2)]),
    station("hk", [team("HK")], { region: "hongkong" })], { ecfMainlandQuota: 5 });
  const m = buildQualification(d, "ecf");
  assert.equal(m.stations.length, 2);
  assert.deepEqual([...m.current.selected.keys()], ["A-1", "A-2", "C-1", "A-3", "B-1"]);
  assert.equal(m.cells.get(1).role, "duplicate");
  assert.equal(m.cells.get(6).role, "duplicate");
});

test("outside takes priority over duplicate beyond the frontier and ECF shows school order", () => {
  const d = data([station("one", [team("A"), team("A", 2, 2)]), station("two", [team("C"), team("A", 1, 2)])], { ecfMainlandQuota: 2 });
  const ecf = buildQualification(d, "ecf");
  assert.equal(ecf.current.frontier, 1);
  assert.equal(ecf.cells.get(3).role, "outside");
  assert.equal(ecf.cells.get(2).role, "outside");
  assert.deepEqual([0, 1, 2, 3].map(p => ecf.cells.get(p).schoolRank), [1, 1, null, null]);
  assert.ok([...buildQualification(d, "wf").cells.values()].every(c => c.schoolRank === null));
  const hk = { ...pending("hk", 115), region: "hongkong" };
  assert.equal(buildQualification(data([...d.stations, hk], { ecfMainlandQuota: 2 }), "ecf").hongkong.id, "hk");
  assert.equal(ecf.hongkong, null);
});

test("pending unique schools bound WF slots; already qualified schools remain alternatives", () => {
  const d = data([station("known", [team("A"), team("B", 1, 2), team("C", 1, 3)]), pending("future", 2)]);
  const m = buildQualification(d, "wf");
  assert.deepEqual([...m.safe], ["A"]);
  assert.equal(m.cells.get(2).certainty, "risk");
  assert.equal(m.conservative.reserved, 1);
});

test("ECF school-cap risk is separate from competition for the overall quota", () => {
  const d = data([station("known", [team("A"), team("A", 2, 2), team("A", 3, 3), team("B", 1, 4)]), pending("future", 3)], { ecfMainlandQuota: 20 });
  const m = buildQualification(d, "ecf");
  assert.ok(m.safe.has("A-1"));
  assert.ok(!m.safe.has("A-2"), "earlier future roster may overlap the second team");
  assert.ok(!m.safe.has("A-3"));
  assert.match(m.cells.get(4).reason, /同校/);
  assert.equal(m.cells.get(4).pressure.level, "low");
  assert.equal(m.cells.get(4).pressure.schoolTolerance, 0);
  assert.equal(m.cells.get(4).pressure.schoolRisk, true);
});

test("ECF skips direct member overlap without transitive merging or spending school slots", () => {
  const roster = (number, members, rank) => ({ ...team("A", number, rank), members });
  const a = roster(1, ["a", "b", "c"], 1);
  const b = roster(2, ["c", "d", "e"], 2);
  const c = roster(3, ["e", "f", "g"], 3);
  const d = data([station("one", [a, b, c, roster(4, ["h", "i", "j"], 4), team("B", 1, 5)])], { ecfMainlandQuota: 4 });
  const before = structuredClone(d);
  const m = buildQualification(d, "ecf");
  assert.deepEqual([...m.current.selected.keys()], ["A-1", "A-3", "A-4", "B-1"]);
  assert.equal(m.cells.get(1).role, "duplicate");
  assert.equal(m.current.visited.get(1).duplicateOf, "A-1");
  assert.equal(m.cells.get(2).schoolRank, 2);
  assert.equal(m.cells.get(3).schoolRank, 3);
  assert.equal(m.cells.get(2).pressure.schoolTolerance, 1);
  assert.deepEqual(d, before);
  assert.deepEqual([...m.conservative.selected.keys()], [...m.current.selected.keys()]);
});

test("ICPC overlap is scoped to school, normalizes visible names and preserves retained roster", () => {
  const a = { ...team("A"), members: ["Ａｌｉｃｅ", "b", "c"] };
  const b = { ...team("A", 2, 2), members: [" alice ", "d", "e"] };
  const foreign = { ...team("B", 1, 3), members: ["Alice", "d", "e"] };
  const m = buildQualification(data([station("one", [a, b, foreign])]), "ecf");
  assert.deepEqual([...m.current.selected.keys()], ["A-1", "B-1"]);
  assert.deepEqual(m.current.selected.get("A-1").team.members, a.members);
  assert.equal(m.current.selected.get("A-1").team.rank, 1);
  const partial = { ...b, members: ["Alice"], identityComplete: false };
  assert.equal(buildQualification(data([station("one", [a, partial])]), "ecf").cells.get(1).role, "duplicate");
});

test("WF overlap suppresses duplicate candidates without changing school allocation", () => {
  const a = { ...team("A"), members: ["a", "b", "c"] };
  const b = { ...team("A", 2), members: ["c", "d", "e"] };
  const c = { ...team("A", 3), members: ["e", "f", "g"] };
  const d = data([station("a", [a, team("B", 1, 2)]), station("b", [b, team("C", 1, 2)]),
    station("c", [c, team("D", 1, 2)])]);
  const m = buildQualification(d, "wf");
  assert.deepEqual([...m.current.selected.keys()], ["A", "B", "C"]);
  assert.equal(m.cells.get(1).role, "duplicate");
  assert.equal(m.cells.get(2).role, "candidate", "discarded B does not connect A to C");
});

test("future overlapping roster can replace an ECF team even with ample quotas", () => {
  const a = team("A");
  const d = data([pending("first", 2), station("known", [a])], { ecfMainlandQuota: 20 });
  const m = buildQualification(d, "ecf");
  const cell = [...m.cells.values()][0];
  assert.equal(cell.certainty, "risk");
  assert.equal(cell.pressure.level, "low");
  assert.equal(cell.pressure.schoolRisk, false);
  assert.equal(cell.pressure.overlapRisk, true);
  const future = { ...team("A", 2), members: [a.members[0], "new1", "new2"] };
  const completed = [{ ...m.stations[0], status: "finished", entries: [future] }, m.stations[1]];
  assert.equal(scanQualification(completed, "ecf", 20, 3).selected.has(a.key), false);
});

test("Zhejiang Sci-Tech keeps Wuhan and skips overlapping Chengdu without consuming a second slot", () => {
  const snapshot = JSON.parse(fs.readFileSync(new URL("../static/data/qualification/2026-2027.json", import.meta.url)));
  const m = buildQualification(snapshot, "ecf");
  const cells = [...m.cells.values()].filter(c => c.team.school === "浙江理工大学");
  const wuhan = cells.find(c => c.team.name === "是啊，吃什么");
  const chengdu = cells.find(c => c.team.name === "happy baby");
  assert.equal(wuhan.role, "selected");
  assert.equal(wuhan.schoolRank, 1);
  assert.equal(chengdu.role, "duplicate");
  assert.equal(chengdu.schoolRank, null);
  assert.equal(m.current.visited.get(chengdu.position).duplicateOf, wuhan.team.key);
  assert.equal(m.current.selected.size, 230);
  const chosen = [...m.current.selected.values()].map(e => e.team);
  for (let i = 0; i < chosen.length; i++) for (let j = 0; j < i; j++) {
    if (chosen[i].schoolKey === chosen[j].schoolKey) assert.ok(!chosen[i].members.some(name => chosen[j].members.includes(name)));
  }
});

test("slot pressure distinguishes robust, majority-insertion and half-or-less insertion cases", () => {
  const d = data([station("known", ["A", "B", "C", "D", "E", "F"].map((s, i) => team(s, 1, i + 1))), pending("future", 5)], { ecfMainlandQuota: 6 });
  const m = buildQualification(d, "ecf");
  const p = [...m.cells.values()].filter(c => c.role === "selected").map(c => c.pressure);
  assert.deepEqual(p.map(p => [p.slotTolerance, p.pendingBefore, p.level]), [
    [5, 0, "low"], [4, 1, "low"], [3, 2, "low"], [2, 3, "medium"], [1, 4, "high"], [0, 5, "high"],
  ]);
  assert.ok(p.every(p => p.schoolTolerance === 2));
  assert.equal(m.current.selected.size, 6);
});

test("every claimed safe ECF team survives exhaustive small future outcomes", () => {
  const known = station("known", [team("A"), team("B", 1, 2), team("A", 2, 3), team("C", 1, 4)]);
  const d = data([known, pending("future", 2)], { ecfMainlandQuota: 5 });
  const m = buildQualification(d, "ecf");
  const choices = [team("A"), team("A", 2), team("A", 3), team("B"), team("C"), team("X"),
    { ...team("A", 4), members: ["A1a", "A2a", "bridge"] }];
  for (const first of choices) for (const second of choices) {
    if (first.key === second.key) continue;
    const completed = [m.stations[0], { ...m.stations[1], status: "finished", entries: [first, second] }];
    const result = scanQualification(completed, "ecf", 5, 3);
    for (const key of m.safe) assert.ok(result.selected.has(key), `${key} lost for ${first.key}/${second.key}`);
  }
});

test("ties and incomplete identity cannot produce false certainty; invalid snapshots fail", () => {
  const partial = { ...team("A"), members: ["a", "b"], identityComplete: false };
  const m = buildQualification(data([station("one", [partial, team("B", 1, 1)])]), "ecf");
  assert.equal(m.safe.size, 0);
  const bad = data([station("one", [team("A")])]);
  bad.stations[0].effectiveCount = 3;
  assert.throws(() => validateQualification(bad), /effective count/);
  const fake = data([pending("future")]);
  fake.stations[0].teams.push(team("X"));
  assert.throws(() => validateQualification(fake), /no results/);
});

test("published November snapshot is deterministic, excludes stars, and preserves inputs", () => {
  const d = JSON.parse(fs.readFileSync(new URL("../static/data/qualification/2026-2027.json", import.meta.url)));
  const before = JSON.stringify(d);
  const wf = buildQualification(d, "wf");
  const ecf = buildQualification(d, "ecf");
  assert.deepEqual(wf.stations.map(s => s.title), ["沈阳", "西安", "武汉", "南昌", "上海", "南京", "成都", "香港"]);
  assert.deepEqual(wf.stations.filter(s => s.status === "finished").map(s => [s.officialCount, s.effectiveCount]), [[401, 398], [402, 393], [369, 369], [332, 326], [319, 315]]);
  assert.deepEqual([...wf.safe], ["北京大学", "清华大学", "同济大学"]);
  assert.equal(wf.current.selected.size, 8);
  assert.equal(ecf.current.selected.size, 230);
  assert.equal(ecf.boundaryRow, 90);
  assert.equal(ecf.safe.size, 2);
  assert.equal(JSON.stringify(d), before);
  assert.deepEqual(buildQualification(d, "wf").safe, wf.safe);
});
