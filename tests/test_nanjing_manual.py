import hashlib
import json
from pathlib import Path


def test_nanjing_manual_identity_snapshot_and_source():
    root = Path(__file__).parents[1] / "static"
    roster = json.loads((root / "data/rosters/icpc-2026-nanjing.json").read_text("utf-8"))
    preview = json.loads((root / "data/previews/icpc-2026-nanjing.json").read_text("utf-8"))
    source = roster["source"]
    assert source["pdfPages"] == "15–28"
    assert source["pages"] == "11–24"
    assert source["file"] == preview["teamSource"]["title"] == (
        "第51届ICPC亚洲区域赛南京竞赛手册.pdf"
    )
    assert source["url"] == preview["teamSource"]["url"] == "./sources/icpc-2026-nanjing-manual.pdf"
    assert hashlib.sha256((root / source["url"]).read_bytes()).hexdigest() == source["sha256"] == (
        "5f52e783acdde591df68517e2b74740c08c8ed386b2afa2abc62358a2b142d8e"
    )
    assert hashlib.sha256(json.dumps(
        roster["teams"], ensure_ascii=False, separators=(",", ":")
    ).encode()).hexdigest() == "aae493476fe8dd5f2095440e3a612b2d32950e39d4c449ec234b1837bbd8271e"
    assert len(roster["teams"]) == len(preview["teams"]) == 374
    assert sum(not t["excluded"] for t in roster["teams"]) == 332
    assert sum(len(t["members"]) for t in roster["teams"]) == 1122
    assert len({t["id"] for t in preview["teams"]}) == 374
    for i, (identity, team) in enumerate(zip(roster["teams"], preview["teams"], strict=True)):
        assert team["sourceIndex"] == i
        assert {k: team[k] for k in ("school", "name", "excluded")} == {
            k: identity[k] for k in ("school", "name", "excluded")
        }
        assert [m["name"] for m in team["members"]] == identity["members"]
    assert roster["teams"][337]["members"][0] == "柳晛"
    assert roster["teams"][352]["members"][2] == "佘欣颐"
    assert roster["teams"][358]["members"][2] == "逄锦骏"
    assert roster["teams"][301]["name"] == "奶界最忧郁之龙"
    assert roster["teams"][330]["name"] == "藍二橋"
    assert roster["teams"][-2:] == [
        {"school": "北京大学附属中学", "name": "unmazing",
         "members": ["许远正", "陈雨翔", "方铨铎"], "excluded": True},
        {"school": "杭州市第二中学", "name": "盒子信U队",
         "members": ["杨子宸", "胡墨", "吴思辰"], "excluded": True},
    ]
    assert source["transcriptionNotes"][0]["status"] == "provisional"
    assert preview["sourceSnapshots"]["xcpcrating"] == "2026-11-03T19:53:29.276259+00:00"
    assert preview["sourceSnapshots"]["xcpcElo"] == "2026-11-04T13:55:31.904Z"
    assert preview["sourcesFetchedAt"] == "2026-11-05T11:20:57.079123+00:00"
    assert preview["medalSources"]["addedContestIds"] == []
