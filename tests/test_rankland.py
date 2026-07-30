import httpx

from core import RankLandClient, normalize_srk_contest


def srk(title: str = "Regional") -> dict:
    return {
        "contest": {"title": title, "startAt": "2025-10-01T09:00:00+08:00"},
        "problems": [{"alias": "A"}, {"alias": "B"}],
        "rows": [
            {
                "rank": 1,
                "user": {
                    "id": "observer",
                    "name": "Observer",
                    "organization": "Other",
                    "official": False,
                    "teamMembers": [{"name": "Nobody"}],
                },
                "score": {"value": 3, "time": [20, "min"]},
                "statuses": [{"result": "AC", "tries": 1}],
            },
            {
                "rank": 2,
                "user": {
                    "id": "first",
                    "name": {"zh-CN": "第一队"},
                    "organization": "大学一",
                    "official": True,
                    "teamMembers": [{"name": "甲"}],
                },
                "score": {"value": 2, "time": [100, "min"]},
                "statuses": [{"result": "AC", "tries": 1}],
            },
            {
                "rank": 3,
                "user": {
                    "id": "tie",
                    "name": "Tie",
                    "organization": "大学二",
                    "official": True,
                    "teamMembers": [{"name": "乙"}],
                },
                "score": {"value": 2, "time": [100, "min"]},
                "statuses": [{"result": "WA", "tries": 2}],
            },
            {
                "rank": 4,
                "user": {
                    "id": "last",
                    "name": "Last",
                    "organization": "大学三",
                    "official": True,
                    "teamMembers": [{"name": "丙"}],
                },
                "score": {"value": 1, "time": [200, "min"]},
                "statuses": [],
            },
        ],
    }


def test_srk_normalization_excludes_unofficial_from_rank_and_preserves_ties() -> None:
    contest = normalize_srk_contest(srk(), contest_uk="regional", series="icpc2025")
    assert [team.rank for team in contest.teams] == [0, 1, 1, 3]
    assert contest.teams[2].has_activity is True
    assert contest.teams[3].has_activity is True


def test_srk_normalization_cleans_school_display_qualifier() -> None:
    payload = srk()
    payload["rows"][1]["user"]["organization"] = "北京师范大学珠海校区（非独立法人）"
    payload["rows"][2]["user"]["organization"] = " 香港中文大學 ( 非獨立法人 ) "
    contest = normalize_srk_contest(payload, contest_uk="regional", series="icpc2025")
    assert contest.teams[1].school_name == "北京师范大学珠海校区"
    assert contest.teams[2].school_name == "香港中文大學"


def test_rankland_client_walks_collection_detail_file_and_cdn() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        calls.append(url)
        if url.endswith("/public/collections/official"):
            data = {
                "content": {
                    "root": {
                        "children": [
                            {
                                "type": 2,
                                "uniqueKey": "dir-icpc2025",
                                "name": "icpc2025",
                                "children": [
                                    {"type": 1, "uniqueKey": "regional", "name": "Regional"}
                                ],
                            }
                        ]
                    }
                }
            }
            return httpx.Response(200, json={"success": True, "code": 0, "data": data})
        if url.endswith("/public/contests/regional"):
            data = {
                "uk": "regional",
                "title": "Regional",
                "startAt": "2025-10-01T09:00:00+08:00",
                "srkFileID": "file-1",
            }
            return httpx.Response(200, json={"success": True, "code": 0, "data": data})
        if url.endswith("/public/files/file-1"):
            data = {"url": "https://cdn.example/regional.srk.json", "hashValue": "abc"}
            return httpx.Response(200, json={"success": True, "code": 0, "data": data})
        if url == "https://cdn.example/regional.srk.json":
            return httpx.Response(200, json=srk())
        return httpx.Response(404)

    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = RankLandClient(client=http, attempts=1)
    contests = client.fetch_collection("icpc2025")
    assert len(contests) == 1
    assert contests[0].provenance is not None
    assert contests[0].provenance.file_id == "file-1"
    assert len(calls) == 4
