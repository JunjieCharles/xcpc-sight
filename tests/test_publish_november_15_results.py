import hashlib
import json
from pathlib import Path

import pytest

from scripts import publish_november_15_2026_results as publisher


def test_two_results_are_offline_repeatable_and_validated_before_writes(tmp_path, monkeypatch):
    fixtures = Path(__file__).parent / "fixtures/review"
    results = []
    for cid, collection, pid, start in [
        ("icpc2026test", "icpc2026", "shenyang", "09:00"),
        ("ccpc2026test", "ccpc2026", "jingzhou", "09:40"),
    ]:
        payload = json.loads((fixtures / "contest.srk.json").read_text(encoding="utf-8"))
        payload["contest"]["startAt"] = f"2026-11-15T{start}:00+08:00"
        payload["series"] = [{"rule": {"preset": "ICPC", "options": {
            "count": {"value": [1, 1, 1]},
        }}}]
        raw = json.dumps(payload).encode()
        (tmp_path / f"{cid}.srk.json").write_bytes(raw)
        results.append((cid, collection, pid, "file", hashlib.sha256(raw).hexdigest()))
        (tmp_path / "previews").mkdir(exist_ok=True)
        (tmp_path / f"previews/{pid}.json").write_bytes((fixtures / "preview.json").read_bytes())
    monkeypatch.setattr(publisher, "INPUTS", ())
    monkeypatch.setattr(publisher, "RESULTS", tuple(results))
    (tmp_path / "reviews").mkdir()
    review_path = tmp_path / "reviews/2026-2027.json"
    old = json.loads((fixtures / "results.json").read_text(encoding="utf-8"))
    review_path.write_text(json.dumps(old), encoding="utf-8")
    previews = {p: p.read_bytes() for p in (tmp_path / "previews").iterdir()}

    publisher.publish(tmp_path, tmp_path, tmp_path)
    review = json.loads(review_path.read_text(encoding="utf-8"))
    assert review["contests"][:-2] == old["contests"]
    assert [c["id"] for c in review["contests"][-2:]] == ["icpc2026test", "ccpc2026test"]
    assert [c["source"]["sha256"] for c in review["contests"][-2:]] == [r[-1] for r in results]
    ratings_path = tmp_path / "series/2026-2027.json"
    ratings = json.loads(ratings_path.read_text(encoding="utf-8"))
    # Rating keeps the existing CCPC-first rule, even with a later start time.
    assert [c["id"] for c in ratings["contests"]] == ["ccpc2026test", "icpc2026test"]
    assert all(p.read_bytes() == raw for p, raw in previews.items())
    before = [p.read_bytes() for p in (review_path, ratings_path)]
    publisher.publish(tmp_path, tmp_path, tmp_path)
    assert [p.read_bytes() for p in (review_path, ratings_path)] == before

    srk = tmp_path / "ccpc2026test.srk.json"
    srk.write_bytes(srk.read_bytes() + b" ")
    with pytest.raises(ValueError, match="ccpc2026test: SRK SHA-256 mismatch"):
        publisher.publish(tmp_path, tmp_path, tmp_path)
    assert [p.read_bytes() for p in (review_path, ratings_path)] == before
