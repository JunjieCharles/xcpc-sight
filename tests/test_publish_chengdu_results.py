import hashlib
import json
from pathlib import Path

import pytest

from scripts import publish_chengdu_2026_results as publisher


def test_publish_is_offline_repeatable_and_preserves_other_reviews(tmp_path, monkeypatch):
    fixtures = Path(__file__).parent / "fixtures/review"
    payload = json.loads((fixtures / "contest.srk.json").read_text(encoding="utf-8"))
    payload["contest"]["startAt"] = "2026-10-25T09:10:00+08:00"
    payload["series"] = [{"rule": {"preset": "ICPC", "options": {
        "count": {"value": [1, 1, 1]},
    }}}]
    raw = json.dumps(payload).encode()
    srk = tmp_path / f"{publisher.CONTEST_ID}.srk.json"
    srk.write_bytes(raw)
    monkeypatch.setattr(publisher, "INPUTS", ())
    monkeypatch.setattr(publisher, "SHA256", hashlib.sha256(raw).hexdigest())
    (tmp_path / "previews").mkdir()
    preview = (fixtures / "preview.json").read_bytes()
    (tmp_path / "previews/icpc-2026-chengdu.json").write_bytes(preview)
    (tmp_path / "reviews").mkdir()
    review_path = tmp_path / "reviews/2026-2027.json"
    old = json.loads((fixtures / "results.json").read_text(encoding="utf-8"))
    review_path.write_text(json.dumps(old), encoding="utf-8")

    publisher.publish(tmp_path, tmp_path, tmp_path)
    review = json.loads(review_path.read_text(encoding="utf-8"))
    assert review["contests"][:-1] == old["contests"]
    assert review["contests"][-1]["source"]["sha256"] == publisher.SHA256
    ratings = json.loads((tmp_path / "series/2026-2027.json").read_text(encoding="utf-8"))
    assert [c["id"] for c in ratings["contests"]] == [publisher.CONTEST_ID]
    assert (tmp_path / "previews/icpc-2026-chengdu.json").read_bytes() == preview
    outputs = [review_path, tmp_path / "series/2026-2027.json"]
    before = [p.read_bytes() for p in outputs]
    publisher.publish(tmp_path, tmp_path, tmp_path)
    assert [p.read_bytes() for p in outputs] == before

    srk.write_bytes(raw + b" ")
    with pytest.raises(ValueError, match="icpc2026chengdu: SRK SHA-256 mismatch"):
        publisher.publish(tmp_path, tmp_path, tmp_path)
    assert [p.read_bytes() for p in outputs] == before
