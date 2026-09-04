import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  createPreviewStore,
  readPreviewQuery,
  searchPreviewTeams,
  sortPreviewTeams,
  validatePreview,
  writePreviewQuery,
} from "../static/js/preview.mjs";

function fixture() {
  const metricSources = [
    { id: "xcpcrating", title: "XCPC Rating", url: "https://example.test/rating" },
    { id: "xcpcElo", title: "XCPC Elo", url: "https://example.test/elo" },
  ];
  const member = (name, xcpcrating, xcpcElo, gold = 0, silver = 0, bronze = 0) => ({
    name,
    ratings: { xcpcrating, xcpcElo },
    medals: { gold, silver, bronze },
  });
  return {
    schemaVersion: 1,
    seriesId: "2026-2027",
    seriesTitle: "2026–2027 ICPC + CCPC",
    id: "online-1",
    title: "网络赛一",
    sortAt: "2026-09-06T13:00:00+08:00",
    snapshotDate: "2026-09-04",
    teamSource: { title: "报名系统", url: "https://example.test/teams", note: "静态快照" },
    metricSources,
    matchingPolicy: "先姓名后学校",
    teams: [
      {
        id: "a",
        sourceIndex: 0,
        school: "甲大学",
        name: "Alpha",
        members: [member("甲", 1500, null, 1, 0, 2), member("乙", 1700, 1400, 0, 3, 0)],
        ratings: { xcpcrating: 1700, xcpcElo: 1400 },
        medals: { gold: 1, silver: 3, bronze: 2 },
      },
      {
        id: "b",
        sourceIndex: 1,
        school: "乙大学",
        name: "Beta",
        members: [member("丙", null, 1800, 1, 1, 9)],
        ratings: { xcpcrating: null, xcpcElo: 1800 },
        medals: { gold: 1, silver: 1, bronze: 9 },
      },
    ],
  };
}

test("published 2026-2027 preview satisfies its schema", async () => {
  const document = JSON.parse(await readFile(
    new URL("../static/data/previews/2026-2027.json", import.meta.url),
    "utf8",
  ));
  assert.equal(validatePreview(document), document);
  assert.equal(document.teams.length, 2535);
  assert.ok(document.teams.every((team) => team.members.length > 0));
});

test("validates member maxima and team medal totals", () => {
  const document = fixture();
  assert.equal(validatePreview(document), document);
  const brokenRating = structuredClone(document);
  brokenRating.teams[0].ratings.xcpcrating = 1500;
  assert.throws(() => validatePreview(brokenRating), /highest member value/);
  const brokenMedals = structuredClone(document);
  brokenMedals.teams[0].medals.bronze = 1;
  assert.throws(() => validatePreview(brokenMedals), /member total/);
});

test("searches school, team and all member names", () => {
  const teams = fixture().teams;
  assert.deepEqual(searchPreviewTeams(teams, "Alpha 乙").map(({ id }) => id), ["a"]);
  assert.deepEqual(searchPreviewTeams(teams, "", ["乙大学"]).map(({ id }) => id), ["b"]);
});

test("sorts nullable ratings last and medals by gold, silver, bronze", () => {
  const teams = fixture().teams;
  assert.deepEqual(sortPreviewTeams(teams, "xcpcrating", "desc").map(({ id }) => id), ["a", "b"]);
  assert.deepEqual(sortPreviewTeams(teams, "xcpcElo", "desc").map(({ id }) => id), ["b", "a"]);
  assert.deepEqual(sortPreviewTeams(teams, "medals", "desc").map(({ id }) => id), ["a", "b"]);
});

test("round trips preview sorting through URL state", () => {
  const next = writePreviewQuery("https://example.test/?series=2026-2027", {
    view: "preview",
    sort: "medals",
    order: "asc",
  });
  assert.equal(next.searchParams.get("view"), "preview");
  assert.deepEqual(readPreviewQuery(next), { previewSort: "medals", previewOrder: "asc" });
});

test("loads preview relative to the site index", async () => {
  const document = fixture();
  const seen = [];
  const fetchImpl = async (url) => {
    seen.push(url);
    return { ok: true, status: 200, json: async () => document };
  };
  const store = createPreviewStore("https://example.test/sub/data/index.json", fetchImpl);
  const loaded = await store.getSeries({
    id: "2026-2027",
    previewPath: "previews/2026-2027.json",
  });
  assert.equal(loaded, document);
  assert.deepEqual(seen, ["https://example.test/sub/data/previews/2026-2027.json"]);
});
