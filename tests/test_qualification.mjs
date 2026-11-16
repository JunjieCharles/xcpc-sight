import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

test("both boards use one pending label with pressure colors and distinct guaranteed places", () => {
  for (const level of ["low", "medium", "high"]) {
    const cell = { role: "selected", certainty: "risk", pressure: { level } };
    assert.deepEqual(cellPresentation(cell), {
      className: `pressure-${level}`, label: "当前出线 待定", detail: "具体名额尚未锁定",
    });
    assert.equal(cell.certainty, "risk");
    assert.equal(cellPresentation({ ...cell, certainty: "safe" }).label, "确定有名额");
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
  assert.ok(m.safe.has("A-2"));
  assert.ok(!m.safe.has("A-3"));
  assert.match(m.cells.get(4).reason, /同校/);
  assert.equal(m.cells.get(4).pressure.level, "low");
  assert.equal(m.cells.get(4).pressure.schoolTolerance, 0);
  assert.equal(m.cells.get(4).pressure.schoolRisk, true);
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
  const choices = [team("A"), team("A", 2), team("A", 3), team("B"), team("C"), team("X")];
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
  assert.equal(ecf.boundaryRow, 89);
  assert.equal(ecf.safe.size, 3);
  assert.equal(JSON.stringify(d), before);
  assert.deepEqual(buildQualification(d, "wf").safe, wf.safe);
});
