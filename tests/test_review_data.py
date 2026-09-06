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


def test_offline_generator_is_deterministic_and_rejects_wrong_hash(tmp_path):
    raw = (FIXTURES / "contest.srk.json").read_bytes()
    output = tmp_path / "review.json"
    command = [
        sys.executable, "scripts/generate_review_data.py",
        "--srk", str(FIXTURES / "contest.srk.json"),
        "--preview", str(FIXTURES / "preview.json"),
        "--contest-id", "actual-one", "--file-id", "fixture",
        "--file-url", "https://example.test/fixture.srk.json",
        "--output", str(output), "--sha256", hashlib.sha256(raw).hexdigest(),
    ]
    root = Path(__file__).parents[1]
    subprocess.run(command, cwd=root, check=True, capture_output=True)
    first = output.read_bytes()
    subprocess.run(command, cwd=root, check=True, capture_output=True)
    assert output.read_bytes() == first
    failed = subprocess.run([*command[:-1], "0" * 64], cwd=root, capture_output=True)
    assert failed.returncode != 0
    assert b"SHA-256 mismatch" in failed.stderr
    assert output.read_bytes() == first
