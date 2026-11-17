import copy
import hashlib
import json
from pathlib import Path

import pytest

from core.normalization import DefaultNormalizer
from scripts.generate_qualification_data import build_document, project_station

FIXTURE = Path(__file__).parent / "fixtures/review/contest.srk.json"


def raw():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["rows"] = data["rows"][:1]
    data["rows"][0]["user"]["teamMembers"] = [{"name": name} for name in ["甲", "乙", "丙"]]
    return data


def test_projection_identity_ignores_team_name_member_order_and_coaches():
    payload = raw()
    normalizer = DefaultNormalizer()
    spec = {"id": "one", "title": "fixture", "region": "mainland"}
    first = project_station(spec, payload, normalizer)
    original = copy.deepcopy(payload)
    payload["rows"][0]["user"]["teamMembers"].reverse()
    payload["rows"][0]["user"]["teamMembers"].insert(0, {"name": "老师", "role": "coach"})
    payload["rows"][0]["user"]["name"] = "renamed"
    second = project_station({**spec, "id": "two"}, payload, normalizer)
    assert first["teams"][0]["key"] == second["teams"][0]["key"]
    assert "老师" not in second["teams"][0]["members"]
    assert first == project_station(spec, original, normalizer)


def test_partial_rosters_remain_distinct_and_stars_are_excluded():
    payload = raw()
    payload["rows"][0]["user"]["teamMembers"].pop()
    first = project_station({"id": "one"}, payload, DefaultNormalizer())
    second = project_station({"id": "two"}, payload, DefaultNormalizer())
    assert first["teams"][0]["identityComplete"] is False
    assert first["teams"][0]["key"] != second["teams"][0]["key"]
    payload["rows"][0]["user"]["official"] = False
    empty = project_station({"id": "one"}, payload, DefaultNormalizer())
    assert empty["officialCount"] == empty["effectiveCount"] == 0


def test_pinned_source_hash_failure_and_offline_build(tmp_path):
    payload = raw()
    binary = json.dumps(payload).encode()
    (tmp_path / "one.srk.json").write_bytes(binary)
    config = {"stations": [{"id": "one", "status": "finished"}]}
    source = {"sha256": hashlib.sha256(binary).hexdigest()}
    review = {"contests": [{"id": "one", "source": source}]}
    doc = build_document(config, [tmp_path], review, {})
    assert doc["stations"][0]["officialCount"] == 1
    assert doc == build_document(config, [tmp_path], review, {})
    ccpc_config = {**config, "kind": "ccpcf"}
    ccpc = build_document(ccpc_config, [tmp_path], review, {})
    assert ccpc["stations"][0]["teams"][0]["memberKeys"]
    assert ccpc == build_document(ccpc_config, [tmp_path], review, {})
    source["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="SHA-256"):
        build_document(config, [tmp_path], review, {})
    with pytest.raises(ValueError, match="not found"):
        build_document(config, [tmp_path / "missing"], review, {})


def test_host_metadata_matches_config_and_survives_projection():
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / "config/qualification-2026-2027.json").read_text(encoding="utf-8"))
    snapshot_path = root / "static/data/qualification/2026-2027.json"
    published = json.loads(snapshot_path.read_text(encoding="utf-8"))
    by_id = {station["id"]: station for station in published["stations"]}
    for spec in config["stations"]:
        assert by_id[spec["id"]]["hostSchool"] == spec["hostSchool"]
        assert by_id[spec["id"]]["hostSource"] == spec["hostSource"]
    spec = config["stations"][0]
    projected = project_station(spec, raw(), DefaultNormalizer())
    assert projected["hostSchool"] == spec["hostSchool"]
    assert projected["hostSource"] == spec["hostSource"]


def test_ccpcf_projection_preserves_duplicate_unranked_records_for_member_merging():
    payload = raw()
    original = payload["rows"][0]
    duplicate = copy.deepcopy(original)
    duplicate["user"]["id"] = "inactive-duplicate"
    duplicate["score"] = {"value": 0, "time": [0, "s"]}
    duplicate["statuses"] = []
    payload["rows"].append(duplicate)
    result = project_station({"id": "ccpc-test"}, payload, DefaultNormalizer(), ccpcf=True)
    assert result["officialCount"] == 2
    assert result["effectiveCount"] == 1
    first, second = result["teams"]
    assert first["rank"] == 0
    assert first["key"] != second["key"]
    assert first["memberKeys"] == second["memberKeys"]
    assert first["memberKeys"] == sorted(first["memberKeys"])


def test_ccpcf_snapshot_matches_config_and_review_sources():
    root = Path(__file__).resolve().parents[1]
    config = json.loads(
        (root / "config/ccpcf-qualification-2026-2027.json").read_text(encoding="utf-8")
    )
    published = json.loads(
        (root / "static/data/qualification/ccpcf-2026-2027.json").read_text(encoding="utf-8")
    )
    review = json.loads((root / "static/data/reviews/2026-2027.json").read_text(encoding="utf-8"))
    sources = {c["id"]: c["source"] for c in review["contests"]}
    for key, value in config.items():
        if key != "stations":
            assert published[key] == value
    for spec, station in zip(config["stations"], published["stations"], strict=True):
        assert station["id"] == spec["id"]
        if spec["status"] == "finished":
            assert station["source"] == sources[spec["id"]]
            assert all(t["memberKeys"] for t in station["teams"])
        else:
            assert station == {**spec, "teams": []}
