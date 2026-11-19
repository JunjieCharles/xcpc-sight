import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import { buildCcpcfQualification, ccpcfRegionEdges } from "../static/js/ccpcf-qualification.mjs";
import { validateQualification, loadQualification } from "../static/js/qualification.mjs";
import { validateIndex } from "../static/js/data.mjs";

const source = { title: "fixture", url: "https://example.org/rules" };
const team = (school, key, rank, members = [`${key}a`, `${key}b`, `${key}c`]) => ({
  key, school, schoolKey: school, rank, name: key, members, memberKeys: members,
  identityComplete: members.length === 3, solved: rank ? 1 : 0,
});
const station = (id, teams = [], pending = false) => ({ id: String(id), title: String(id), date: `2026-11-0${id}`,
  region: "mainland", status: pending ? "pending" : "finished", source,
  officialCount: teams.length, effectiveCount: teams.filter(t => t.solved > 0).length,
  teams: teams.toSorted((a, b) => a.rank - b.rank),
});
const data = (stations, firstQuota = 2, secondQuota = 1) => ({ schemaVersion: 1, kind: "ccpcf", seriesId: "test",
  asOf: "2026-11-17", disclaimer: "民间数据，仅供参考，不代表官方结果", ruleSeason: "2025-2026",
  ruleNotice: "fixture", rules: [source], stations, firstQuota, secondQuota });
const selected = (model, i) => model.channels[i].selected.map(g => g.schoolKey).sort();

test("channel outlines use station ranks including ties, independently of school representatives", () => {
  const m = buildCcpcfQualification(data([
    station(1, [team("A", "a1", 1), team("A", "a2", 2), team("B", "b1", 2), team("C", "c1", 4)]),
    station(2, [team("D", "d1", 1)]), station(3, [], true),
  ]));
  assert.deepEqual(m.channels.map(c => c.cutoffRank), [1, 2]);
  assert.deepEqual(m.channels.map(c => c.regionRows), [[1, 1, 1], [3, 1, 2]]);
  assert.equal(m.boundaryRow, 3);
  assert.deepEqual(ccpcfRegionEdges(0, 1, [3, 1, 2]), ["top", "bottom"]);
  assert.deepEqual(ccpcfRegionEdges(1, 0, [3, 1, 2]), ["left", "right"]);
  assert.deepEqual(ccpcfRegionEdges(2, 0, [3, 1, 2]), ["left", "right", "bottom"]);
  assert.deepEqual(ccpcfRegionEdges(1, 2, [3, 1, 2]), ["left", "right", "bottom"]);
  assert.deepEqual(ccpcfRegionEdges(1, 1, [3, 1, 2]), []);
  assert.deepEqual(ccpcfRegionEdges(0, 0, [0, 0]), []);
  assert.deepEqual(ccpcfRegionEdges(0, 0, [1]), ["top", "left", "right", "bottom"]);
  const empty = buildCcpcfQualification(data([station(1, [], true)]));
  assert.deepEqual(empty.channels.map(c => c.regionRows), [[0], [0]]);
});

test("CCPCF merges overlapping members transitively, takes best rank, isolates schools", () => {
  const d = data([
    station(1, [team("A", "a", 1, ["x", "y", "z"]), team("A", "b", 3, ["p", "q", "r"]), team("A", "d", 4), team("B", "e", 5, ["x", "y", "z"])]),
    station(2, [team("A", "bridge", 2, ["z", "p", "v"])]),
  ]);
  const before = structuredClone(d);
  const m = buildCcpcfQualification(d);
  assert.equal(m.schools.get("A").length, 2);
  assert.equal(m.schools.get("A")[0].appearances.length, 3);
  assert.equal(m.schools.get("A")[0].bestRank, 1);
  assert.equal(m.schools.get("A")[1].bestRank, 4);
  assert.deepEqual(selected(m, 0), ["A", "B"]);
  assert.deepEqual(selected(m, 1), ["A"]);
  assert.equal([...m.cells.values()].filter(c => c.role === "duplicate").length, 2);
  assert.deepEqual(d, before);
  assert.deepEqual(selected(buildCcpcfQualification({ ...d, stations: [...d.stations].reverse() }), 0), selected(m, 0));
});

test("channels rank independently and include all threshold ties, never force 100/20 exact counts", () => {
  const d = data([station(1, [team("A", "a1", 1), team("A", "a2", 9), team("A", "a3", 11),
    team("B", "b1", 4), team("B", "b2", 9), team("C", "c1", 4), team("D", "d1", 5)])]);
  const m = buildCcpcfQualification(d);
  assert.deepEqual(selected(m, 0), ["A", "B", "C"]);
  assert.deepEqual(selected(m, 1), ["A", "B"]);
  assert.deepEqual(m.channels[0].entries.map(g => g.channelRank), [1, 2, 2, 4]);
  assert.equal(m.channels[1].cutoffRank, 9);
  assert.ok(m.channels.flatMap(c => c.selected).every(g => g.certainty === "safe"));
  assert.equal([...m.cells.values()].find(c => c.team.key === "a3").role, "outside");
});

test("unranked duplicate and bridging records do not claim slots or lose their identity links", () => {
  const d = data([station(1, [team("A", "inactive", 0, ["x", "y", "z"]), team("A", "a", 2, ["x", "u", "v"]),
    team("A", "b", 5, ["z", "p", "q"]), team("B", "empty", 0)])]);
  const m = buildCcpcfQualification(d);
  assert.equal(m.schools.get("A").length, 1);
  assert.equal(m.schools.has("B"), false);
  assert.equal(m.channels[0].selected[0].bestRank, 2);
  assert.equal(m.cells.size, 2);
  assert.equal(m.channels[1].selected.length, 0);
});

test("ranked zero-solve teams remain eligible and all-pending snapshots are empty", () => {
  const zero = { ...team("A", "zero", 1), solved: 0 };
  assert.deepEqual(selected(buildCcpcfQualification(data([station(1, [zero])])), 0), ["A"]);
  const empty = buildCcpcfQualification(data([station(1, [], true)]));
  assert.equal(empty.cells.size, 0);
  assert.equal(empty.channels[0].cutoffRank, null);
  assert.equal(empty.boundaryRow, 0);
  assert.equal(empty.maxRows, 1);
});

test("pending rank bounds count strictly better results; second slots retain future merge risk", () => {
  const d = data([station(1, [team("A", "a1", 1), team("A", "a2", 2), team("B", "b", 3)]), station(2, [], true)], 2, 10);
  const m = buildCcpcfQualification(d);
  assert.equal(m.channels[0].entries[0].certainty, "safe");
  assert.equal(m.channels[0].entries[1].certainty, "risk");
  assert.equal(m.channels[1].entries[0].certainty, "risk");
  assert.equal(m.channels[1].entries[0].pressure.level, "low");
  assert.equal(m.channels[1].entries[0].pressure.schoolRisk, true);
  const bridged = buildCcpcfQualification(data([d.stations[0], station(2, [team("A", "bridge", 1, ["a1a", "a2a", "new"])])], 2, 10));
  assert.equal(bridged.channels[1].selected.length, 0, "a future bridge really can remove a second school slot");
  const tied = buildCcpcfQualification(data([station(1, [team("A", "a", 1), team("B", "b", 1)]), station(2, [], true)], 1));
  assert.ok(tied.channels[0].selected.every(g => g.certainty === "safe"));
});

test("enumerated future fields preserve every guaranteed first school slot", () => {
  const known = station(1, [team("A", "a", 1), team("B", "b", 2), team("C", "c", 3)]);
  const before = buildCcpcfQualification(data([known, station(2, [], true)], 3));
  const safe = before.channels[0].selected.filter(g => g.certainty === "safe").map(g => g.schoolKey);
  for (const a of ["A", "B", "C", "X"]) for (const b of ["A", "B", "C", "Y"]) {
    const after = buildCcpcfQualification(data([known, station(2, [team(a, "future1", 1), team(b, "future2", 2)])], 3));
    for (const school of safe) assert.ok(selected(after, 0).includes(school));
  }
});

test("partial rosters prevent a guaranteed second slot and invalid identities fail with station context", () => {
  const d = data([station(1, [team("A", "a", 1, ["x"]), team("A", "b", 2)])]);
  assert.equal(buildCcpcfQualification(d).channels[1].selected[0].certainty, "risk");
  d.stations[0].teams[0].memberKeys = ["x", "x"];
  assert.throws(() => validateQualification(d), /stations\[0\].*member keys/);
});

test("published CCPCF snapshot is pinned independently and includes the current three stations", () => {
  const d = JSON.parse(fs.readFileSync(new URL("../static/data/qualification/ccpcf-2026-2027.json", import.meta.url)));
  const m = buildCcpcfQualification(d);
  assert.deepEqual(m.stations.map(s => s.id), ["ccpc2026changchun", "ccpc2026leshan", "ccpc2026jingzhou", "ccpc2026xiamen"]);
  assert.deepEqual(m.channels.map(c => [c.selected.length, c.cutoffRank]), [[101, 92], [20, 33]]);
  assert.deepEqual(m.channels.map(c => c.regionRows), [[92, 92, 92, 92], [33, 33, 33, 33]]);
  assert.deepEqual(m.channels.map(c => c.selected.filter(g => g.certainty === "safe").length), [56, 0]);
  assert.equal(m.pendingCount, 1);
  assert.equal(d.ruleSeason, "2025-2026");
  const index = JSON.parse(fs.readFileSync(new URL("../static/data/index.json", import.meta.url)));
  validateIndex(index);
  const entry = index.series.find(s => s.id === d.seriesId);
  assert.equal(entry.ccpcfQualificationPath, "qualification/ccpcf-2026-2027.json");
  entry.ccpcfQualificationPath = entry.qualificationPath;
  assert.throws(() => validateIndex(structuredClone(index)));
});

test("loader selects the CCPCF path and rejects mismatched kinds", async () => {
  const previous = globalThis.fetch;
  const d = data([station(1, [team("A", "a", 1)])]);
  let requested;
  globalThis.fetch = async url => { requested = String(url); return { ok: true, json: async () => d }; };
  try {
    await loadQualification({ id: "test", ccpcfQualificationPath: "ccpcf.json" }, "https://example.org/data/index.json", "ccpcf");
    assert.equal(requested, "https://example.org/data/ccpcf.json");
    await assert.rejects(loadQualification({ id: "test", qualificationPath: "wf.json" }, "https://example.org/data/index.json"), /mode mismatch/);
  } finally { globalThis.fetch = previous; }
});

test("Xiamen shows the published ranking and detects displacement of an individual school team", () => {
  const read = path => JSON.parse(fs.readFileSync(new URL(`../static/data/${path}.json`, import.meta.url)));
  const snapshot = read("qualification/ccpcf-2026-2027");
  const preview = read("previews/ccpc-2026-xiamen");
  const m = buildCcpcfQualification(snapshot, [preview]);
  const rows = m.stations.at(-1).entries;
  assert.equal(m.pendingCount, 1);
  assert.equal(rows.length, 300);
  assert.deepEqual(new Set(rows.map(t => t.key)), new Set(preview.teams.filter(t => !t.excluded).map(t => t.id)));
  assert.deepEqual(rows.slice(0, 2).map(t => [t.name, t.rank]), [["柚子超玩会", 1], ["Oblivion", 2]]);
  assert.deepEqual(m.channels.map(c => ["safe", "uncertain", "displaced"].map(
    status => c.selected.filter(g => g.outlook === status).length)), [[14, 80, 7], [2, 8, 10]]);
  assert.equal(m.safe.size, 16);
  const zju = [...m.cells.values()].find(c => c.role === "selected" && c.team.name === "猫没有通过图灵测试");
  assert.equal(zju.schoolRank, 2);
  assert.equal(zju.outlook, "displaced");
  assert.equal(m.current.selected.size, 121);
  const forecast = [...m.cells.values()].filter(cell => cell.role === "forecast");
  assert.deepEqual([1, 2, null].map(slot => forecast.filter(cell => cell.forecastSlot === slot).length),
    [13, 10, 277]);
});

test("Xiamen projects both qualification channels from the chosen power dimension", () => {
  const read = path => JSON.parse(fs.readFileSync(new URL(`../static/data/${path}.json`, import.meta.url)));
  const snapshot = read("qualification/ccpcf-2026-2027");
  const preview = read("previews/ccpc-2026-xiamen");
  for (const [metric, secondTeam, unranked, qualifying, displaced] of [
    ["power", "Oblivion", 0, 23, 17],
    ["xcpcrating", "呆呆鸡", 0, 23, 15],
    ["xcpcElo", "Oblivion", 0, 19, 15],
    ["currentSeason", "队线大冲浪", 4, 22, 14],
    ["onlineRanks", "中山大学-眉毛", 6, 21, 15],
  ]) {
    const model = buildCcpcfQualification(snapshot, [preview], metric);
    assert.deepEqual(model.forecastMetrics.map(option => option.id), ["power", ...preview.powerMetrics]);
    const rows = model.stations.at(-1).entries;
    assert.equal(rows[1].name, secondTeam);
    assert.equal(rows.filter(team => team.rank === null).length, unranked);
    assert.ok(rows.slice(rows.length - unranked).every(team => team.rank === null));
    assert.equal([...model.cells.values()].filter(cell => cell.forecastSlot).length, qualifying);
    assert.equal([...model.current.selected.values()].filter(group => group.outlook === "displaced").length, displaced);
  }
  assert.throws(() => buildCcpcfQualification(snapshot, [preview], "previousSeason"), RangeError);
});

test("one shared metric ranks each forecast station independently", () => {
  const previews = [];
  const stations = [2, 3].map(n => {
    const dimensions = n === 2 ? ["currentSeason", "xcpcElo", "previousSeason"] : ["xcpcElo", "currentSeason"];
    const teams = ["A", "B"].map((name, i) => ({
      id: name, name, school: name + n, members: [{ name }], sourceIndex: i,
      medals: { gold: 0, silver: 0, bronze: 0 }, ratings: { currentSeason: i, xcpcElo: 1 - i, previousSeason: i },
    }));
    const previewId = "p" + n;
    previews.push({ id: previewId, teams, powerMetrics: dimensions, metricSources: dimensions.map(id => ({ id, title: id })) });
    return { ...station(n, [], true), previewId, previewIdentities: Object.fromEntries(
      teams.map(t => [t.id, { schoolKey: t.school, memberKeys: [t.name] }])) };
  });
  for (const [metric, leader] of [["currentSeason", "B"], ["xcpcElo", "A"]]) {
    const model = buildCcpcfQualification(data(stations, 1, 1), previews, metric);
    assert.deepEqual(model.forecastMetrics.map(option => option.id), ["power", "currentSeason", "xcpcElo"]);
    for (const col of [0, 1]) {
      assert.equal(model.cells.get(col).team.name, leader);
      assert.equal(model.cells.get(col).forecastSlot, 1);
      assert.equal(model.cells.get(2 + col).forecastSlot, null);
    }
  }
  const partial = buildCcpcfQualification(data([...stations, station(4, [], true)]), previews, "xcpcElo");
  assert.equal(partial.cells.get(1).team.name, "A");
  assert.equal(partial.cells.get(1).forecastSlot, null);
});

function verifyTeamOutlooks(past, entrants, quotas) {
  const pending = { ...station(2, [], true), previewId: "p",
    previewIdentities: Object.fromEntries(entrants.map(t => [t.key, { schoolKey: t.schoolKey, memberKeys: t.memberKeys }])) };
  const preview = { id: "p", metricSources: [{ id: "currentSeason" }], powerMetrics: ["currentSeason"],
    teams: entrants.map((t, i) => ({ id: t.key, sourceIndex: i, name: t.name, school: t.school,
      members: t.members.map(name => ({ name })), ratings: { currentSeason: t.rank ? 100 - t.rank : null } })) };
  const m = buildCcpcfQualification(data([past, pending], ...quotas), [preview]);
  const finish = teams => buildCcpcfQualification(data([past, station(2, teams)], ...quotas));
  const ranks = new Map(m.stations[1].entries.map(t => [t.key, t.rank ?? 0]));
  const predicted = finish(entrants.map(t => ({ ...t, rank: ranks.get(t.key) })));
  const entrantKeys = new Set(entrants.map(t => t.key));
  const actualSlots = new Map([...predicted.cells.values()]
    .filter(c => entrantKeys.has(c.team.key) && c.role === "selected")
    .map(c => [c.team.key, c.schoolRank]));
  for (const cell of m.cells.values()) {
    if (cell.role === "forecast") assert.equal(cell.forecastSlot, actualSlots.get(cell.team.key) ?? null);
  }
  const possible = [];
  function enumerate(order, rest) {
    possible.push(finish([...order.map((t, i) => ({ ...t, rank: i + 1 })),
      ...rest.map(t => ({ ...t, rank: 0, solved: 0 }))]));
    for (const t of rest) enumerate([...order, t], rest.filter(other => other !== t));
  }
  enumerate([], entrants);
  for (const channel of m.channels) {
    for (const g of channel.selected) {
      const retained = result => result.channels.some(c => c.selected.some(winner =>
        winner.appearances.find(a => a.column === 0 && a.team.rank)?.team.key === g.representative.team.key));
      const expected = !retained(predicted) ? "displaced" : possible.every(retained) ? "safe" : "uncertain";
      assert.equal(g.outlook, expected, `${g.schoolKey}, team ${g.representative.team.key}`);
    }
  }
  return m;
}

test("both team channels agree with exhaustive finishes, including bridges, ties and unranked entrants", () => {
  const past = station(1, [team("A", "a1", 1), team("A", "a2", 4), team("B", "b1", 2),
    team("B", "b2", 5), team("C", "c1", 3), team("C", "c2", 6)]);
  const entrants = [team("D", "d1", 1), team("D", "d2", 2), team("C", "c3", 2),
    team("B", "bridge", 4, ["b1a", "b2a", "new"]), team("E", "e", 0)];
  const m = verifyTeamOutlooks(past, entrants, [2, 2]);
  assert.deepEqual(m.stations[1].entries.map(t => t.rank), [1, 2, 2, 4, null]);
});

test("same-school overtakes can change channels or eliminate a team while its school retains slots", () => {
  const past = station(1, [team("A", "a1", 2), team("A", "a2", 4), team("B", "b1", 1),
    team("B", "b2", 3), team("C", "c1", 2)]);
  const entrants = [team("A", "a3", 1), team("A", "a4", 2), team("A", "again", 3, ["a2a"]),
    team("B", "b3", 4), team("D", "d1", 5)];
  for (const quotas of [[1, 1], [2, 1], [3, 2]]) verifyTeamOutlooks(past, entrants, quotas);
});
