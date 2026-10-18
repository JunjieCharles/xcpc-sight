import copy
import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from core import DataValidationError, normalize_srk_contest, project_review_contest
from rating import project_static_data_index

FIXTURES = Path(__file__).parent / "fixtures" / "review"


def fixture():
    preview = json.loads((FIXTURES / "preview.json").read_text(encoding="utf-8"))
    raw = json.loads((FIXTURES / "contest.srk.json").read_text(encoding="utf-8"))
    contest = normalize_srk_contest(raw, contest_uk="actual-one", series="test-series")
    return preview, contest


def test_srk_to_review_to_frontend_offline():
    preview, contest = fixture()
    projected = project_review_contest(preview, contest)
    committed = json.loads((FIXTURES / "results.json").read_text(encoding="utf-8"))
    assert projected == committed["contests"][0]
    assert projected["source"]["url"] == "https://rl.algoux.cn/ranklist/actual-one"
    assert projected["teams"][1]["hasActivity"] is False
    assert projected["teams"][1]["actualRank"] is None
    assert projected["teams"][4]["hasActivity"] is True  # WA but zero solves
    assert projected["teams"][0]["actualRank"] == projected["teams"][3]["actualRank"]
    script = """
      import fs from 'node:fs';
      import {validateReview, buildReviewAnalysis} from './static/js/review.mjs';
      import {validatePreview} from './static/js/preview.mjs';
      const input=JSON.parse(fs.readFileSync(0,'utf8'));
      const p=validatePreview(input.preview);
      const r=validateReview(input.review,[p]);
      const a=buildReviewAnalysis(p,r.contests[0]);
      console.log(JSON.stringify(a.rows.map(t=>[t.id,t.previewRank,t.actualRank])));
    """
    process = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        input=json.dumps({"preview": preview, "review": committed}),
        text=True,
        capture_output=True,
        check=True,
        cwd=Path(__file__).parents[1],
    )
    assert json.loads(process.stdout) == [["a", 1, 1], ["c", 2, 3], ["d", 3, 1]]


def test_matching_handles_punctuation_names_and_full_roster_fallback():
    preview, contest = fixture()
    preview["teams"][0]["name"] = "！！！"
    contest = replace(
        contest, teams=(replace(contest.teams[0], team_name="!!!"), *contest.teams[1:])
    )
    assert project_review_contest(preview, contest)["teams"][0]["resultTeamId"] == "result-a"
    preview["teams"][0]["name"] = "renamed team"
    assert project_review_contest(preview, contest)["teams"][0]["resultTeamId"] == "result-a"


def test_missing_or_ambiguous_result_is_an_error_not_absence():
    preview, contest = fixture()
    with pytest.raises(DataValidationError, match="preview team a.*candidates"):
        project_review_contest(preview, replace(contest, teams=contest.teams[1:]))
    duplicate = replace(contest.teams[0], team_id="second-a")
    ambiguous = replace(contest, teams=(*contest.teams, duplicate))
    with pytest.raises(DataValidationError, match="preview team a.*candidates"):
        project_review_contest(preview, ambiguous)
    fixed = project_review_contest(preview, ambiguous, overrides={"a": "result-a"})
    assert fixed["teams"][0]["resultTeamId"] == "result-a"
    with pytest.raises(DataValidationError, match="unknown override"):
        project_review_contest(preview, contest, overrides={"unknown": "result-a"})
    with pytest.raises(DataValidationError, match="preview team b"):
        project_review_contest(preview, contest, overrides={"b": "result-a"})


def test_unofficial_teams_never_match_and_input_is_not_mutated():
    preview, contest = fixture()
    before = copy.deepcopy(preview)
    project_review_contest(preview, contest)
    assert preview == before
    unofficial = replace(contest.teams[0], official=False)
    with pytest.raises(DataValidationError, match="preview team a"):
        project_review_contest(preview, replace(contest, teams=(unofficial, *contest.teams[1:])))


def test_explicit_unofficial_results_and_medals_preserve_preview_and_scores():
    preview, contest = fixture()
    original = copy.deepcopy(preview)
    changed = replace(
        contest, teams=(replace(contest.teams[0], official=False), *contest.teams[1:])
    )
    medals = {t.team_id: None for t in changed.teams if t.official}
    medals[contest.teams[3].team_id] = "gold"
    projected = project_review_contest(preview, changed,
                                       unofficial_results={"a": "result-a"}, result_medals=medals)
    assert projected["hasMedals"] is True
    assert projected["teams"][0] == {
        "previewTeamId": "a", "resultTeamId": "result-a", "resultStatus": "unofficial",
        "hasActivity": None, "actualRank": None, "actualMedal": None,
    }
    assert projected["teams"][3]["actualMedal"] == "gold"
    assert preview == original
    for invalid in ({"a": "result-b"}, {"unknown": "result-a"}):
        with pytest.raises(DataValidationError, match="unofficial"):
            project_review_contest(preview, changed, unofficial_results=invalid)
    with pytest.raises(DataValidationError, match="overlap"):
        project_review_contest(preview, changed, unofficial_results={"a": "result-a"},
                               overrides={"a": "result-b"})
    with pytest.raises(DataValidationError, match="exactly"):
        project_review_contest(preview, contest, result_medals={})
    with pytest.raises(DataValidationError, match="invalid result medal"):
        project_review_contest(preview, changed, result_medals={**medals, "result-d": "platinum"})
    with pytest.raises(DataValidationError, match="inactive"):
        project_review_contest(preview, changed, result_medals={**medals, "result-b": "gold"})


def test_excluded_preview_teams_are_omitted_without_requiring_a_result():
    preview, contest = fixture()
    preview["teams"][0]["excluded"] = True
    before = copy.deepcopy(preview)
    for teams in (contest.teams, contest.teams[1:]):
        projected = project_review_contest(preview, replace(contest, teams=teams))
        assert len(projected["teams"]) == len(preview["teams"]) - 1
        assert "a" not in {row["previewTeamId"] for row in projected["teams"]}
    assert preview == before


def test_explicitly_removed_result_is_not_an_absence_and_ranks_are_rebuilt():
    preview, contest = fixture()
    original = copy.deepcopy(preview)
    updated = replace(contest, teams=contest.teams[1:])
    mapping = {"a": "result-a"}
    projected = project_review_contest(preview, updated, removed_results=mapping)
    assert projected["teams"][0] == {
        "previewTeamId": "a", "resultTeamId": "result-a", "resultStatus": "removed",
        "hasActivity": None, "actualRank": None,
    }
    assert projected["teams"][1]["hasActivity"] is False
    assert projected["teams"][3]["actualRank"] == 2  # an unlisted team remains first
    assert projected["teams"][2]["actualRank"] == 4  # previously fifth
    assert projected["teams"][4]["hasActivity"] is True  # zero solves with activity
    assert preview == original
    assert mapping == {"a": "result-a"}
    with pytest.raises(DataValidationError, match="expected unique unused result"):
        project_review_contest(preview, updated)


@pytest.mark.parametrize("mapping, message", [
    ({"unknown": "old"}, "unknown removed"),
    ({"a": ""}, "nonempty string"),
    ({"a": 1}, "nonempty string"),
    ({"a": "old", "b": "old"}, "duplicate old"),
    ({"a": "result-b"}, "still present"),
    ({"a": "result-a", "b": "old"}, "still matches"),
    ([], "must map"),
])
def test_removed_results_reject_invalid_or_still_matching_entries(mapping, message):
    preview, contest = fixture()
    updated = replace(contest, teams=contest.teams[1:])
    with pytest.raises(DataValidationError, match=message):
        project_review_contest(preview, updated, removed_results=mapping)


def test_removed_results_cannot_overlap_overrides_or_hide_unofficial_results():
    preview, contest = fixture()
    updated = replace(contest, teams=contest.teams[1:])
    with pytest.raises(DataValidationError, match="overlap"):
        project_review_contest(preview, updated, overrides={"a": "result-b"},
                               removed_results={"a": "result-a"})
    updated = replace(
        contest, teams=(replace(contest.teams[0], official=False), *contest.teams[1:])
    )
    with pytest.raises(DataValidationError, match="still present"):
        project_review_contest(preview, updated, removed_results={"a": "result-a"})


def test_index_supports_multiple_previews_and_review_references():
    preview, contest = fixture()
    second = {**preview, "id": "preview-two", "sortAt": "2026-09-10T13:00:00+08:00"}
    review = {
        "schemaVersion": 1,
        "seriesId": preview["seriesId"],
        "contests": [project_review_contest(preview, contest)],
    }
    publications = [(preview, "previews/one.json"), (second, "previews/two.json")]
    index = project_static_data_index(
        [], preview_publications=publications, review_publications=[(review, "reviews/test.json")]
    )
    entry = index["series"][0]
    assert entry["previewPath"] == "previews/one.json"
    assert entry["previews"] == [
        {"id": preview["id"], "path": "previews/one.json"},
        {"id": second["id"], "path": "previews/two.json"},
    ]
    assert entry["reviewPath"] == "reviews/test.json"
    with pytest.raises(DataValidationError, match="duplicate preview"):
        project_static_data_index([], preview_publications=[(preview, "a"), (preview, "b")])
    review["contests"][0]["previewId"] = "unknown"
    with pytest.raises(DataValidationError, match="unknown preview"):
        project_static_data_index(
            [],
            preview_publications=publications,
            review_publications=[(review, "reviews/test.json")],
        )


@pytest.mark.parametrize("remove_result", [False, True])
def test_offline_generator_is_deterministic_and_rejects_wrong_hash(tmp_path, remove_result):
    raw = (FIXTURES / "contest.srk.json").read_bytes()
    srk_path = FIXTURES / "contest.srk.json"
    removal_args = []
    if remove_result:
        document = json.loads(raw)
        document["rows"] = [r for r in document["rows"] if r["user"]["id"] != "result-a"]
        raw = json.dumps(document).encode()
        srk_path = tmp_path / "updated.srk.json"
        srk_path.write_bytes(raw)
        mapping = tmp_path / "removed.json"
        mapping.write_text(json.dumps({"a": "result-a"}), encoding="utf-8")
        removal_args = ["--removed-results", str(mapping)]
    output = tmp_path / "review.json"
    command = [
        sys.executable, "scripts/generate_review_data.py",
        *removal_args, "--srk", str(srk_path),
        "--preview", str(FIXTURES / "preview.json"),
        "--contest-id", "actual-one", "--file-id", "fixture",
        "--file-url", "https://example.test/fixture.srk.json",
        "--output", str(output), "--sha256", hashlib.sha256(raw).hexdigest(),
    ]
    root = Path(__file__).parents[1]
    subprocess.run(command, cwd=root, check=True, capture_output=True)
    first = output.read_bytes()
    if remove_result:
        removed = json.loads(first)["contests"][0]["teams"][0]
        assert removed["resultStatus"] == "removed"
        assert removed["hasActivity"] is None
    subprocess.run(command, cwd=root, check=True, capture_output=True)
    assert output.read_bytes() == first
    failed = subprocess.run([*command[:-1], "0" * 64], cwd=root, capture_output=True)
    assert failed.returncode != 0
    assert b"SHA-256 mismatch" in failed.stderr
    assert output.read_bytes() == first


def test_offline_generator_publishes_medals_source_and_explicit_unofficial_result(tmp_path):
    payload = json.loads((FIXTURES / "contest.srk.json").read_text(encoding="utf-8"))
    payload["rows"][0]["user"]["official"] = False
    payload["series"] = [{"rule": {"preset": "ICPC", "options": {
        "count": {"value": [1, 1, 1]},
    }}}]
    raw = json.dumps(payload).encode()
    source = tmp_path / "contest.srk.json"
    source.write_bytes(raw)
    mapping = tmp_path / "unofficial.json"
    mapping.write_text(json.dumps({"a": "result-a"}), encoding="utf-8")
    output = tmp_path / "review.json"
    command = [
        sys.executable, "scripts/generate_review_data.py", "--srk", str(source),
        "--preview", str(FIXTURES / "preview.json"), "--contest-id", "actual-one",
        "--file-id", "fixture", "--file-url", "https://example.test/results.json",
        "--sha256", hashlib.sha256(raw).hexdigest(), "--output", str(output),
        "--medals", "--unofficial-results", str(mapping),
        "--source-url", "https://example.test/board", "--source-title", "Official board",
    ]
    subprocess.run(command, check=True, capture_output=True)
    first = output.read_bytes()
    contest = json.loads(first)["contests"][0]
    assert contest["hasMedals"]
    assert contest["source"]["url"] == "https://example.test/board"
    assert contest["source"]["title"] == "Official board"
    assert contest["teams"][0]["resultStatus"] == "unofficial"
    assert contest["teams"][0]["actualMedal"] is None
    assert all("actualMedal" in team for team in contest["teams"])
    assert any(team["actualMedal"] for team in contest["teams"])
    subprocess.run(command, check=True, capture_output=True)
    assert output.read_bytes() == first
    mapping.write_text(json.dumps({"a": "result-b"}), encoding="utf-8")
    failed = subprocess.run(command, capture_output=True)
    assert failed.returncode != 0
    assert b"current unofficial results" in failed.stderr
    assert output.read_bytes() == first
