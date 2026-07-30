from __future__ import annotations

import csv
import io
from urllib.parse import parse_qs

import httpx
import pytest

from core import (
    DataValidationError,
    NowcoderClient,
    NowcoderError,
    normalize_nowcoder_page,
    nowcoder_csv_fieldnames,
    nowcoder_csv_rows,
    nowcoder_leaderboard_to_contest,
)


def score(problem_id: int, *, accepted: bool = True) -> dict:
    return {
        "problemId": problem_id,
        "accepted": accepted,
        "acceptedTime": 123456 if accepted else None,
        "failedCount": 1,
        "firstBlood": False,
        "submit": True,
        "finishJudge": True,
        "waitingJudgeCount": 0,
        "submissionId": 987 if accepted else None,
        "score": 0.0,
        "fullScore": 0.0,
        "timeConsumption": 0,
    }


def standing(uid: int, ranking: int) -> dict:
    return {
        "ranking": ranking,
        "uid": uid,
        "userName": f"队伍{uid}",
        "school": "测试大学",
        "team": True,
        "teamMemberUids": [uid + 1000, uid + 2000],
        "acceptedCount": 1,
        "penaltyTime": 60000,
        "totalScore": 0.0,
        "fullScore": 0.0,
        "colorLevel": 7,
        "scoreList": [score(101)],
    }


def payload(
    *,
    page: int = 1,
    rows: list[dict] | None = None,
    rank_count: int = 2,
    page_count: int = 1,
    contest_id: int = 133876,
) -> dict:
    if rows is None:
        rows = [standing(1, 1), standing(2, 2)]
    return {
        "msg": "OK",
        "code": 0,
        "data": {
            "problemData": [
                {"problemId": 101, "name": "A", "acceptedCount": 2, "submitCount": 3}
            ],
            "rankData": rows,
            "isContestFinished": True,
            "basicInfo": {
                "contestId": contest_id,
                "pageCurrent": page,
                "pageCount": page_count,
                "pageSize": 50,
                "rankCount": rank_count,
                "contestBeginTime": 1000,
                "contestEndTime": 2000,
                "rankType": "ICPC",
                "onlyContestRankApplied": True,
            },
        },
    }


def test_normalize_page_preserves_native_fields() -> None:
    page = normalize_nowcoder_page(payload(), contest_id=133876, requested_page=1)

    assert page.problems[0].name == "A"
    assert page.standings[0].user_name == "队伍1"
    assert page.standings[0].team_member_uids == (1001, 2001)
    assert page.standings[0].penalty_time_ms == 60000
    assert page.standings[0].scores[0].accepted_time_ms == 123456


def test_client_sends_required_query_headers_and_assembles_pages() -> None:
    requests: list[httpx.Request] = []
    rows = [standing(index, index) for index in range(1, 52)]

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        query = parse_qs(request.url.query.decode())
        page = int(query["page"][0])
        page_rows = rows[:50] if page == 1 else rows[50:]
        return httpx.Response(
            200,
            json=payload(page=page, rows=page_rows, rank_count=51, page_count=2),
        )

    http = httpx.Client(transport=httpx.MockTransport(handler))
    leaderboard = NowcoderClient(client=http, attempts=1).fetch_leaderboard(133876)

    assert len(leaderboard.standings) == 51
    assert [request.url.params["page"] for request in requests] == ["1", "1", "2"]
    assert requests[0].url.params["limit"] == "50"
    assert requests[1].url.params["limit"] == "1000000"
    assert requests[2].url.params["limit"] == "51"
    assert all(request.url.params["onlyContestRank"] == "true" for request in requests)
    assert requests[0].headers["referer"].endswith("/acm/contest/133876")
    assert requests[0].headers["user-agent"]


def test_client_retries_transient_http_status() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429 if calls == 1 else 200, json=payload())

    http = httpx.Client(transport=httpx.MockTransport(handler))
    leaderboard = NowcoderClient(
        client=http, attempts=2, retry_base_delay=0
    ).fetch_leaderboard(133876)

    assert leaderboard.rank_count == 2
    assert calls == 2


def test_business_error_is_source_specific() -> None:
    with pytest.raises(NowcoderError, match="business error"):
        normalize_nowcoder_page(
            {"code": 123, "msg": "denied"}, contest_id=133876, requested_page=1
        )


def test_page_mismatch_and_duplicate_scores_are_rejected() -> None:
    with pytest.raises(DataValidationError, match="pageCurrent"):
        normalize_nowcoder_page(payload(page=2), contest_id=133876, requested_page=1)

    personal = standing(3, 3)
    personal["team"] = False
    personal["teamMemberUids"] = None
    personal["school"] = None
    personal_page = normalize_nowcoder_page(
        payload(rows=[personal], rank_count=1), contest_id=133876, requested_page=1
    )
    assert personal_page.standings[0].team_member_uids == ()
    assert personal_page.standings[0].school == ""

    invalid = payload()
    invalid["data"]["rankData"][0]["scoreList"].append(score(101))
    with pytest.raises(DataValidationError, match="duplicate problemId"):
        normalize_nowcoder_page(invalid, contest_id=133876, requested_page=1)


def test_client_rejects_incomplete_page() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload(rows=[standing(1, 1)], rank_count=2))

    http = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(DataValidationError, match="has 1 rows, expected 2"):
        NowcoderClient(client=http, attempts=1).fetch_leaderboard(133876)


def test_leaderboard_adapts_to_registration_level_rating_entity() -> None:
    team_row = standing(42, 1)
    team_row["userName"] = "  惡&middot;即&middot;斬  "
    team_row["school"] = "None"
    team_row["teamMemberUids"] = [1, 2, 3]
    http = httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, json=payload(rows=[team_row], rank_count=1)
            )
        )
    )
    leaderboard = NowcoderClient(client=http, attempts=1).fetch_leaderboard(133876)
    contest = nowcoder_leaderboard_to_contest(leaderboard, title="第一场")
    team = contest.teams[0]

    assert contest.contest_id == "nowcoder:133876"
    assert contest.start_at.isoformat() == "1970-01-01T08:00:01+08:00"
    assert team.members == ()
    assert team.rating_competitor.school == "nowcoder"
    assert team.rating_competitor.member == "standing:42"
    assert team.rating_display_member == "惡·即·斬"
    assert team.rating_display_school == ""
    assert team.solved == 1
    assert team.penalty == 60_000


def test_adapter_rebuilds_ranks_instead_of_using_source_ranking() -> None:
    rows = [standing(1, 10), standing(2, 20), standing(3, 30)]
    rows[2]["acceptedCount"] = 0
    rows[2]["penaltyTime"] = 0
    rows[2]["scoreList"] = [
        {
            **score(101, accepted=False),
            "submit": False,
            "failedCount": 0,
        }
    ]
    http = httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, json=payload(rows=rows, rank_count=3)
            )
        )
    )
    leaderboard = NowcoderClient(client=http, attempts=1).fetch_leaderboard(133876)
    contest = nowcoder_leaderboard_to_contest(leaderboard, title="第一场")

    assert [team.rank for team in contest.teams] == [1, 1, 0]


def test_adapter_rejects_unfinished_or_empty_display_name() -> None:
    unfinished = payload(rows=[standing(1, 1)], rank_count=1)
    unfinished["data"]["isContestFinished"] = False
    page = normalize_nowcoder_page(unfinished, contest_id=133876, requested_page=1)
    from core.nowcoder import _assemble

    with pytest.raises(DataValidationError, match="not finished"):
        nowcoder_leaderboard_to_contest(_assemble((page,)), title="第一场")

    empty_name = standing(1, 1)
    empty_name["userName"] = "   "
    page = normalize_nowcoder_page(
        payload(rows=[empty_name], rank_count=1),
        contest_id=133876,
        requested_page=1,
    )
    with pytest.raises(DataValidationError, match="userName"):
        nowcoder_leaderboard_to_contest(_assemble((page,)), title="第一场")


def test_csv_projection_is_ordered_and_unicode_safe() -> None:
    http = httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload()))
    )
    leaderboard = NowcoderClient(client=http, attempts=1).fetch_leaderboard(133876)
    fields = nowcoder_csv_fieldnames(leaderboard)
    rows = nowcoder_csv_rows(leaderboard)

    assert fields[:4] == ("contest_id", "ranking", "uid", "user_name")
    assert fields[-1] == "A_time_consumption"
    assert rows[0]["team_member_uids"] == "[1001,2001]"
    assert rows[0]["A_accepted_time_ms"] == 123456

    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    parsed = list(csv.DictReader(io.StringIO(output.getvalue())))
    assert parsed[0]["user_name"] == "队伍1"
    assert parsed[0]["school"] == "测试大学"
