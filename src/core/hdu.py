from __future__ import annotations

import csv
import io
import json
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx

from .errors import DataValidationError, HduError
from .models import CompetitorId, Contest, TeamResult
from .ranking import rebuild_competition_ranks

DEFAULT_BASE_URL = "https://acm.hdu.edu.cn"
DEFAULT_USERNAME = "guest"
DEFAULT_PASSWORD = "guest"
HDU_SUMMER_2026_SERIES = "hdu-summer-2026"
USER_AGENT = "Mozilla/5.0 (compatible; xcpc-sight/0.1; +https://acm.hdu.edu.cn/)"
_SHANGHAI = ZoneInfo("Asia/Shanghai")
_CONTEST_MARKER = re.compile(r"\bconst\s+contest\s*=\s*")
_TEAM_PATTERN = re.compile(r"^(team\d+)\s+(.+)$", re.IGNORECASE)
_PENALTY_PATTERN = re.compile(r"^(\d+):(\d{2}):(\d{2})$")


@dataclass(frozen=True, slots=True)
class HduContestMetadata:
    contest_id: int
    title: str
    now: datetime
    start: datetime
    end: datetime
    is_code_sharing: bool

    @property
    def is_finished(self) -> bool:
        return self.now >= self.end


@dataclass(frozen=True, slots=True)
class HduStanding:
    rank: int
    team_token: str
    csv_author: str
    team_name: str
    school_name: str
    solved: int
    penalty_seconds: int
    problem_cells: tuple[str, ...]

    @property
    def display_name(self) -> str:
        """Backward-compatible alias for the structured team name."""
        return self.team_name

    @property
    def has_activity(self) -> bool:
        return any(cell.strip() for cell in self.problem_cells)


@dataclass(frozen=True, slots=True)
class HduLeaderboard:
    metadata: HduContestMetadata
    problem_headers: tuple[str, ...]
    standings: tuple[HduStanding, ...]


class _ContestTitleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._depth = 0
        self._contest_info_depth: int | None = None
        self._h2_depth: int | None = None
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._depth += 1
        attributes = {name.casefold(): value or "" for name, value in attrs}
        classes = attributes.get("class", "").casefold().split()
        if self._contest_info_depth is None and "contest-info" in classes:
            self._contest_info_depth = self._depth
        if (
            tag.casefold() == "h2"
            and self._contest_info_depth is not None
            and self._h2_depth is None
        ):
            self._h2_depth = self._depth

    def handle_endtag(self, _tag: str) -> None:
        if self._h2_depth == self._depth:
            self._h2_depth = None
        if self._contest_info_depth == self._depth:
            self._contest_info_depth = None
        self._depth = max(0, self._depth - 1)

    def handle_data(self, data: str) -> None:
        if self._h2_depth is not None:
            self.parts.append(data)


def _parse_title(html: str, contest_id: int) -> str:
    parser = _ContestTitleParser()
    parser.feed(html)
    title = "".join(parser.parts).strip()
    if not title:
        raise DataValidationError(
            f"HDU contest {contest_id}: contest-info h2 title is missing or empty"
        )
    return title


def _parse_contest_object(source: str, contest_id: int) -> dict[str, Any]:
    marker = _CONTEST_MARKER.search(source)
    if marker is None:
        raise DataValidationError(f"HDU contest {contest_id}: const contest metadata is missing")
    try:
        value, _ = json.JSONDecoder().raw_decode(source, marker.end())
    except json.JSONDecodeError as error:
        raise DataValidationError(
            f"HDU contest {contest_id}: const contest metadata is not strict JSON"
        ) from error
    if not isinstance(value, dict):
        raise DataValidationError(f"HDU contest {contest_id}: contest metadata must be an object")
    expected = {"id", "now", "start", "end", "isCodeSharing"}
    if set(value) != expected:
        raise DataValidationError(
            f"HDU contest {contest_id}: contest metadata fields must be {sorted(expected)}, "
            f"got {sorted(value)}"
        )
    return value


def _timestamp(value: Any, path: str) -> datetime:
    if isinstance(value, bool):
        raise DataValidationError(f"{path} must be a timestamp")
    if isinstance(value, (int, float)):
        seconds = value / 1000 if abs(value) >= 100_000_000_000 else value
        try:
            return datetime.fromtimestamp(seconds, tz=UTC).astimezone(_SHANGHAI)
        except (OverflowError, OSError, ValueError) as error:
            raise DataValidationError(f"{path} is outside the supported timestamp range") from error
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise DataValidationError(f"{path} must not be empty")
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as error:
            raise DataValidationError(f"{path} must be an ISO 8601 timestamp") from error
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=_SHANGHAI)
        return parsed.astimezone(_SHANGHAI)
    raise DataValidationError(f"{path} must be a timestamp")


def parse_hdu_metadata(html: str, *, contest_id: int) -> HduContestMetadata:
    if not isinstance(html, str):
        raise TypeError("html must be a string")
    value = _parse_contest_object(html, contest_id)
    actual_id = value["id"]
    if isinstance(actual_id, bool) or not isinstance(actual_id, int):
        raise DataValidationError(f"HDU contest {contest_id}: contest.id must be an integer")
    if actual_id != contest_id:
        raise DataValidationError(
            f"HDU contest {contest_id}: contest.id is {actual_id}, expected {contest_id}"
        )
    sharing = value["isCodeSharing"]
    if not isinstance(sharing, bool):
        raise DataValidationError(
            f"HDU contest {contest_id}: contest.isCodeSharing must be a boolean"
        )
    metadata = HduContestMetadata(
        contest_id=actual_id,
        title=_parse_title(html, contest_id),
        now=_timestamp(value["now"], f"HDU contest {contest_id}: contest.now"),
        start=_timestamp(value["start"], f"HDU contest {contest_id}: contest.start"),
        end=_timestamp(value["end"], f"HDU contest {contest_id}: contest.end"),
        is_code_sharing=sharing,
    )
    if metadata.end < metadata.start:
        raise DataValidationError(f"HDU contest {contest_id}: contest ends before it begins")
    return metadata


def _integer(text: str, path: str, *, positive: bool = False) -> int:
    try:
        value = int(text)
    except ValueError as error:
        raise DataValidationError(f"{path} must be an integer") from error
    if value < (1 if positive else 0):
        qualifier = "positive" if positive else "non-negative"
        raise DataValidationError(f"{path} must be {qualifier}")
    return value


def _penalty_seconds(text: str, path: str) -> int:
    match = _PENALTY_PATTERN.fullmatch(text)
    if match is None:
        raise DataValidationError(f"{path} must use HH:MM:SS")
    hours, minutes, seconds = map(int, match.groups())
    if minutes >= 60 or seconds >= 60:
        raise DataValidationError(f"{path} must use valid HH:MM:SS")
    return hours * 3600 + minutes * 60 + seconds


def parse_hdu_csv(
    data: bytes,
    *,
    metadata: HduContestMetadata,
) -> HduLeaderboard:
    try:
        text = data.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as error:
        raise DataValidationError(
            f"HDU contest {metadata.contest_id}: leaderboard CSV is not strict UTF-8"
        ) from error
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        rows = list(reader)
    except csv.Error as error:
        raise DataValidationError(
            f"HDU contest {metadata.contest_id}: leaderboard CSV is malformed"
        ) from error
    if not rows:
        raise DataValidationError(f"HDU contest {metadata.contest_id}: leaderboard CSV is empty")
    header = rows[0]
    if len(header) < 4 or header[:4] != ["Rank", "Author", "Solved", "Penalty"]:
        raise DataValidationError(
            f"HDU contest {metadata.contest_id}: CSV must start with headers "
            "Rank, Author, Solved, Penalty"
        )
    problem_headers = tuple(header[4:])
    if (
        any(not item.isascii() or not item.isdecimal() for item in problem_headers)
        or len(set(problem_headers)) != len(problem_headers)
    ):
        raise DataValidationError(
            f"HDU contest {metadata.contest_id}: problem headers must be unique numeric IDs"
        )
    standings: list[HduStanding] = []
    seen_tokens: set[str] = set()
    previous_rank = 0
    for line_number, row in enumerate(rows[1:], start=2):
        path = f"HDU contest {metadata.contest_id}: CSV row {line_number}"
        if len(row) != len(header):
            raise DataValidationError(
                f"{path} has {len(row)} fields, expected {len(header)}"
            )
        rank = _integer(row[0].strip(), f"{path} Rank", positive=True)
        if rank < previous_rank:
            raise DataValidationError(f"{path} Rank is not monotonic")
        previous_rank = rank
        author = unescape(row[1].strip())
        match = _TEAM_PATTERN.fullmatch(author)
        if match is None or not match.group(2).strip():
            raise DataValidationError(
                f"{path} Author must use 'teamNNNN <team> <school>'"
            )
        token = match.group(1).casefold()
        display_fields = match.group(2).strip().rsplit(maxsplit=1)
        if len(display_fields) != 2 or any(not field for field in display_fields):
            raise DataValidationError(
                f"{path} Author must contain a team name and school separated by whitespace"
            )
        team_name, school_name = display_fields
        if token in seen_tokens:
            raise DataValidationError(f"{path} contains duplicate team token {token}")
        seen_tokens.add(token)
        solved = _integer(row[2].strip(), f"{path} Solved")
        if solved > len(problem_headers):
            raise DataValidationError(
                f"{path} Solved is {solved}, greater than problem count {len(problem_headers)}"
            )
        standings.append(
            HduStanding(
                rank=rank,
                team_token=token,
                csv_author=author,
                team_name=team_name,
                school_name=school_name,
                solved=solved,
                penalty_seconds=_penalty_seconds(row[3].strip(), f"{path} Penalty"),
                problem_cells=tuple(row[4:]),
            )
        )
    return HduLeaderboard(metadata, problem_headers, tuple(standings))


def hdu_leaderboard_to_contest(
    leaderboard: HduLeaderboard, *, series: str = HDU_SUMMER_2026_SERIES
) -> Contest:
    metadata = leaderboard.metadata
    if not metadata.is_finished:
        raise DataValidationError(f"HDU contest {metadata.contest_id}: contest is not finished")
    teams = rebuild_competition_ranks(
        tuple(
            TeamResult(
                team_id=standing.team_token,
                team_name=standing.team_name,
                school_name=standing.school_name,
                members=(),
                rank=standing.rank,
                solved=standing.solved,
                penalty=standing.penalty_seconds * 1_000,
                official=True,
                has_activity=standing.has_activity,
                rating_competitor=CompetitorId("hdu", standing.team_token),
                rating_display_school=standing.school_name,
                rating_display_member=standing.team_name,
            )
            for standing in leaderboard.standings
        ),
        contest_id=f"hdu:{metadata.contest_id}",
    )
    return Contest(
        contest_id=f"hdu:{metadata.contest_id}",
        title=metadata.title,
        series=series,
        start_at=metadata.start,
        teams=teams,
    )


class HduClient:
    def __init__(
        self,
        *,
        username: str = DEFAULT_USERNAME,
        password: str = DEFAULT_PASSWORD,
        base_url: str = DEFAULT_BASE_URL,
        client: httpx.Client | None = None,
        timeout: float = 15.0,
        attempts: int = 3,
        retry_base_delay: float = 0.25,
    ) -> None:
        if attempts < 1:
            raise ValueError("attempts must be positive")
        if not username or not password:
            raise ValueError("username and password must not be empty")
        self.username = username
        self.password = password
        self.base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self.client = client or httpx.Client(timeout=timeout, follow_redirects=True)
        self.attempts = attempts
        self.retry_base_delay = retry_base_delay

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> HduClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self.attempts):
            try:
                response = self.client.request(method, url, **kwargs)
                if response.status_code not in {408, 429} and response.status_code < 500:
                    if response.status_code == 404:
                        raise HduError("HDU contest or login endpoint was not found")
                    response.raise_for_status()
                    return response
                last_error = HduError(f"transient HDU HTTP {response.status_code}")
            except HduError:
                raise
            except httpx.HTTPError as error:
                last_error = error
            if attempt + 1 < self.attempts:
                time.sleep(self.retry_base_delay * (2**attempt))
        error_name = type(last_error).__name__ if last_error is not None else "unknown error"
        raise HduError(
            f"HDU request failed after {self.attempts} attempts: {error_name}"
        ) from last_error

    def fetch_leaderboard(self, contest_id: int) -> HduLeaderboard:
        if isinstance(contest_id, bool) or not isinstance(contest_id, int) or contest_id <= 0:
            raise ValueError("contest_id must be a positive integer")
        rank_path = f"/contest/rank?cid={contest_id}&export=csv"
        rank_url = f"{self.base_url}{rank_path}"
        redirect = quote(rank_path, safe="")
        login_url = f"{self.base_url}/contest/login?cid={contest_id}&redirect={redirect}"
        problems_url = f"{self.base_url}/contest/problems?cid={contest_id}"
        headers = {"User-Agent": USER_AGENT}
        problems_page = self._request("GET", problems_url, headers=headers)
        try:
            problems_html = problems_page.content.decode("utf-8-sig", errors="strict")
        except UnicodeDecodeError as error:
            raise DataValidationError(
                f"HDU contest {contest_id}: problems metadata HTML is not strict UTF-8"
            ) from error
        metadata = parse_hdu_metadata(problems_html, contest_id=contest_id)
        response = self._request(
            "POST",
            login_url,
            data={"username": self.username, "password": self.password},
            headers=headers,
        )
        if not self._is_csv(response):
            if self._is_login_response(response):
                self._raise_non_csv(contest_id, response)
            response = self._request("GET", rank_url, headers=headers)
        if not self._is_csv(response):
            self._raise_non_csv(contest_id, response)
        return parse_hdu_csv(response.content, metadata=metadata)

    @staticmethod
    def _content_type(response: httpx.Response) -> str:
        return response.headers.get("content-type", "").split(";", 1)[0].strip().casefold()

    @classmethod
    def _is_csv(cls, response: httpx.Response) -> bool:
        return cls._content_type(response) == "text/csv"

    @staticmethod
    def _is_login_response(response: httpx.Response) -> bool:
        return "/contest/login" in response.url.path or b"Contest Login" in response.content

    @classmethod
    def _raise_non_csv(cls, contest_id: int, response: httpx.Response) -> None:
        content_type = cls._content_type(response)
        raise HduError(
            f"HDU authentication/export failed for contest {contest_id}: "
            f"expected text/csv, got {content_type or 'no content type'}"
        )

    def fetch_contest(
        self, contest_id: int, *, series: str = HDU_SUMMER_2026_SERIES
    ) -> Contest:
        return hdu_leaderboard_to_contest(
            self.fetch_leaderboard(contest_id), series=series
        )
