from __future__ import annotations

import json
from urllib.parse import parse_qs

import httpx
import pytest

from core import (
    DataValidationError,
    HduClient,
    HduError,
    hdu_leaderboard_to_contest,
    parse_hdu_csv,
    parse_hdu_metadata,
)

SERIES_TITLE = '2026“钉耙编程”中国大学生算法设计暑期联赛'


def metadata_html(
    *,
    contest_id: int = 1229,
    now: str = "2026-07-24T18:00:00+08:00",
    start: str = "2026-07-24T12:00:00+08:00",
    end: str = "2026-07-24T17:00:00+08:00",
) -> str:
    contest = json.dumps(
        {
            "id": contest_id,
            "now": now,
            "start": start,
            "end": end,
            "isCodeSharing": False,
        },
        separators=(",", ":"),
    )
    return f"""<!doctype html>
<html><head><title>Contest Login</title></head><body>
<section class="contest-info"><div><h2>{SERIES_TITLE}（第一场）</h2></div></section>
<script>const contest = {contest};</script>
</body></html>"""


def csv_bytes(*, bom: bool = False, upper_token: bool = False) -> bytes:
    token = "TEAM0001" if upper_token else "team0001"
    text = (
        "Rank,Author,Solved,Penalty,1001,1002\r\n"
        f"1,{token} 惡&middot;即&middot;斬 测试大学,2,01:02:03,+,\r\n"
        "2,team0042 测试二队 第二大学,0,00:00:00,, -1\r\n"
        "3,team1000 未提交队 第三大学,0,00:00:00,,\r\n"
    )
    return text.encode("utf-8-sig" if bom else "utf-8")


def test_metadata_and_bom_csv_parse_strict_source_contract() -> None:
    metadata = parse_hdu_metadata(metadata_html(), contest_id=1229)
    leaderboard = parse_hdu_csv(csv_bytes(bom=True, upper_token=True), metadata=metadata)

    assert metadata.title == f"{SERIES_TITLE}（第一场）"
    assert metadata.is_finished
    assert metadata.start.isoformat() == "2026-07-24T12:00:00+08:00"
    assert leaderboard.problem_headers == ("1001", "1002")
    assert leaderboard.standings[0].team_token == "team0001"
    assert leaderboard.standings[0].display_name == "惡·即·斬"
    assert leaderboard.standings[0].school_name == "测试大学"
    assert leaderboard.standings[0].penalty_seconds == 3723
    assert leaderboard.standings[1].has_activity
    assert not leaderboard.standings[2].has_activity


def test_client_uses_problems_metadata_and_authenticated_redirect_export() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, text=metadata_html())
        return httpx.Response(
            200,
            content=csv_bytes(),
            headers={"Content-Type": "text/csv; charset=utf-8"},
        )

    http = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    leaderboard = HduClient(
        client=http,
        username="private-user",
        password="private-pass",
        attempts=1,
    ).fetch_leaderboard(1229)

    assert len(leaderboard.standings) == 3
    assert [request.method for request in requests] == ["GET", "POST"]
    assert requests[0].url.path == "/contest/problems"
    assert requests[0].url.params["cid"] == "1229"
    query = parse_qs(requests[1].url.query.decode())
    assert query == {"cid": ["1229"], "redirect": ["/contest/rank?cid=1229&export=csv"]}
    body = requests[1].content.decode()
    assert "username=private-user" in body
    assert "password=private-pass" in body
    assert all("private-" not in str(request.url) for request in requests)


def test_client_follows_successful_post_with_authenticated_rank_get() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/contest/problems":
            return httpx.Response(200, text=metadata_html())
        if request.method == "POST":
            return httpx.Response(302, headers={"Location": "/contest/home"})
        if request.url.path == "/contest/home":
            return httpx.Response(200, text="welcome", headers={"Content-Type": "text/html"})
        return httpx.Response(200, content=csv_bytes(), headers={"Content-Type": "text/csv"})

    leaderboard = HduClient(
        client=httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True),
        attempts=1,
    ).fetch_leaderboard(1229)

    assert leaderboard.metadata.contest_id == 1229
    assert [(request.method, request.url.path) for request in requests] == [
        ("GET", "/contest/problems"),
        ("POST", "/contest/login"),
        ("GET", "/contest/home"),
        ("GET", "/contest/rank"),
    ]
    assert dict(requests[-1].url.params) == {"cid": "1229", "export": "csv"}


def test_default_guest_credentials_are_injected_only_into_post_body() -> None:
    bodies: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text=metadata_html())
        bodies.append(request.content)
        return httpx.Response(200, content=csv_bytes(), headers={"Content-Type": "text/csv"})

    client = HduClient(
        client=httpx.Client(transport=httpx.MockTransport(handler)), attempts=1
    )
    client.fetch_leaderboard(1229)

    assert bodies == [b"username=guest&password=guest"]


def test_adapter_uses_casefolded_team_token_identity_and_problem_activity() -> None:
    metadata = parse_hdu_metadata(metadata_html(), contest_id=1229)
    contest = hdu_leaderboard_to_contest(
        parse_hdu_csv(csv_bytes(upper_token=True), metadata=metadata)
    )

    assert contest.contest_id == "hdu:1229"
    assert contest.series == "hdu-summer-2026"
    assert contest.start_at.isoformat() == "2026-07-24T12:00:00+08:00"
    assert contest.teams[0].rating_competitor.school == "hdu"
    assert contest.teams[0].rating_competitor.member == "team0001"
    assert contest.teams[0].rating_display_member == "惡·即·斬"
    assert contest.teams[0].rating_display_school == "测试大学"
    assert contest.teams[0].penalty == 62
    assert contest.teams[1].has_activity
    assert not contest.teams[2].has_activity


def test_unfinished_contest_is_rejected_at_rating_boundary() -> None:
    metadata = parse_hdu_metadata(
        metadata_html(now="2026-07-24T16:59:59+08:00"), contest_id=1229
    )
    leaderboard = parse_hdu_csv(csv_bytes(), metadata=metadata)

    with pytest.raises(DataValidationError, match="not finished"):
        hdu_leaderboard_to_contest(leaderboard)


@pytest.mark.parametrize(
    ("html", "message"),
    [
        ("<title>Contest Login</title>", "const contest"),
        (metadata_html(contest_id=1230), "contest.id"),
        (metadata_html().replace('"isCodeSharing":false', '"isCodeSharing":0'), "boolean"),
        (metadata_html().replace("class=\"contest-info\"", "class=\"other\""), "h2 title"),
        (
            metadata_html().replace(
                '"isCodeSharing":false', '"extra":1,"isCodeSharing":false'
            ),
            "fields",
        ),
        (metadata_html().replace('"id":1229', "id:1229"), "strict JSON"),
    ],
)
def test_metadata_rejects_missing_mismatched_or_non_strict_fields(
    html: str, message: str
) -> None:
    with pytest.raises(DataValidationError, match=message):
        parse_hdu_metadata(html, contest_id=1229)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"Author,Rank,Solved,Penalty,1001\n", "must start"),
        (b"Rank,Author,Solved,Penalty,1001,1001\n", "numeric IDs"),
        (b"Rank,Author,Solved,Penalty,A\n", "numeric IDs"),
        (b"Rank,Author,Solved,Penalty,1001\n1,user x,0,00:00:00,\n", "teamNNNN"),
        (b"Rank,Author,Solved,Penalty,1001\n1,team1 x school,2,00:00:00,\n", "problem count"),
        (b"Rank,Author,Solved,Penalty,1001\n1,team1 x school,0,1:2:03,\n", "HH:MM:SS"),
        (b"Rank,Author,Solved,Penalty,1001\n1,team1 x school,0,00:60:00,\n", "valid"),
        (b"Rank,Author,Solved,Penalty,1001\n1,team1 x school,0,00:00:00\n", "fields"),
        (
            b"Rank,Author,Solved,Penalty,1001\n"
            b"2,team1 x school,0,00:00:00,\n1,team2 y school,0,00:00:00,\n",
            "monotonic",
        ),
        (
            b"Rank,Author,Solved,Penalty,1001\n"
            b"1,TEAM1 x school,0,00:00:00,\n2,team1 y school,0,00:00:00,\n",
            "duplicate",
        ),
        (b"Rank,Author,Solved,Penalty,1001\n1,team1 \xff,0,00:00:00,\n", "strict UTF-8"),
    ],
)
def test_csv_rejects_invalid_encoding_headers_and_rows(content: bytes, message: str) -> None:
    metadata = parse_hdu_metadata(metadata_html(), contest_id=1229)
    with pytest.raises(DataValidationError, match=message):
        parse_hdu_csv(content, metadata=metadata)


def test_client_rejects_login_html_and_final_non_csv() -> None:
    def login_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/contest/problems":
            return httpx.Response(200, text=metadata_html())
        return httpx.Response(
            200,
            text="<title>Contest Login</title>",
            headers={"Content-Type": "text/html"},
        )

    with pytest.raises(HduError, match="expected text/csv"):
        HduClient(
            client=httpx.Client(transport=httpx.MockTransport(login_handler)), attempts=1
        ).fetch_leaderboard(1229)

    def non_csv_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/contest/problems":
            return httpx.Response(200, text=metadata_html())
        return httpx.Response(200, text="welcome", headers={"Content-Type": "text/html"})

    with pytest.raises(HduError, match="expected text/csv"):
        HduClient(
            client=httpx.Client(transport=httpx.MockTransport(non_csv_handler)), attempts=1
        ).fetch_leaderboard(1229)


def test_client_retries_transient_status() -> None:
    calls = 0

    def retry_handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503)
        if request.method == "GET":
            return httpx.Response(200, text=metadata_html())
        return httpx.Response(200, content=csv_bytes(), headers={"Content-Type": "text/csv"})

    leaderboard = HduClient(
        client=httpx.Client(transport=httpx.MockTransport(retry_handler)),
        attempts=2,
        retry_base_delay=0,
    ).fetch_leaderboard(1229)
    assert leaderboard.metadata.contest_id == 1229
    assert calls == 3
