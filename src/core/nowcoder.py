from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from typing import Any

import httpx

from .errors import DataValidationError, NowcoderError

JsonObject = dict[str, Any]

DEFAULT_BASE_URL = "https://ac.nowcoder.com"
INITIAL_RESULT_LIMIT = 50
MAX_RESULT_LIMIT = 1_000_000
USER_AGENT = "Mozilla/5.0 (compatible; xcpc-sight/0.1; +https://ac.nowcoder.com/)"


@dataclass(frozen=True, slots=True)
class NowcoderProblem:
    problem_id: int
    name: str
    accepted_count: int
    submit_count: int


@dataclass(frozen=True, slots=True)
class NowcoderProblemScore:
    problem_id: int
    accepted: bool
    accepted_time_ms: int | None
    failed_count: int
    first_blood: bool
    submit: bool
    finish_judge: bool
    waiting_judge_count: int
    submission_id: int | None
    score: int | float
    full_score: int | float
    time_consumption: int


@dataclass(frozen=True, slots=True)
class NowcoderStanding:
    ranking: int
    uid: int
    user_name: str
    school: str
    team: bool
    team_member_uids: tuple[int, ...]
    accepted_count: int
    penalty_time_ms: int
    total_score: int | float
    full_score: int | float
    color_level: int | None
    scores: tuple[NowcoderProblemScore, ...]


@dataclass(frozen=True, slots=True)
class NowcoderLeaderboardPage:
    contest_id: int
    page_current: int
    page_count: int
    page_size: int
    rank_count: int
    contest_begin_time_ms: int
    contest_end_time_ms: int
    rank_type: str
    is_contest_finished: bool
    only_contest_rank_applied: bool
    problems: tuple[NowcoderProblem, ...]
    standings: tuple[NowcoderStanding, ...]


@dataclass(frozen=True, slots=True)
class NowcoderLeaderboard:
    contest_id: int
    contest_begin_time_ms: int
    contest_end_time_ms: int
    rank_type: str
    is_contest_finished: bool
    page_count: int
    page_size: int
    rank_count: int
    problems: tuple[NowcoderProblem, ...]
    standings: tuple[NowcoderStanding, ...]


def _object(value: Any, path: str) -> JsonObject:
    if not isinstance(value, dict):
        raise DataValidationError(f"{path} must be an object")
    return value


def _array(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise DataValidationError(f"{path} must be an array")
    return value


def _required(value: Any, expected: type, path: str) -> Any:
    if expected is int and (isinstance(value, bool) or not isinstance(value, int)):
        raise DataValidationError(f"{path} must be an integer")
    if expected is bool and not isinstance(value, bool):
        raise DataValidationError(f"{path} must be a boolean")
    if expected is str and not isinstance(value, str):
        raise DataValidationError(f"{path} must be a string")
    return value


def _number(value: Any, path: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DataValidationError(f"{path} must be a number")
    return value


def _optional_integer(value: Any, path: str) -> int | None:
    if value is None:
        return None
    return _required(value, int, path)


def _problem(raw: Any, path: str) -> NowcoderProblem:
    item = _object(raw, path)
    name = _required(item.get("name"), str, f"{path}.name").strip()
    if not name:
        raise DataValidationError(f"{path}.name must not be empty")
    return NowcoderProblem(
        problem_id=_required(item.get("problemId"), int, f"{path}.problemId"),
        name=name,
        accepted_count=_required(item.get("acceptedCount"), int, f"{path}.acceptedCount"),
        submit_count=_required(item.get("submitCount"), int, f"{path}.submitCount"),
    )


def _score(raw: Any, path: str) -> NowcoderProblemScore:
    item = _object(raw, path)
    return NowcoderProblemScore(
        problem_id=_required(item.get("problemId"), int, f"{path}.problemId"),
        accepted=_required(item.get("accepted"), bool, f"{path}.accepted"),
        accepted_time_ms=_optional_integer(item.get("acceptedTime"), f"{path}.acceptedTime"),
        failed_count=_required(item.get("failedCount"), int, f"{path}.failedCount"),
        first_blood=_required(item.get("firstBlood"), bool, f"{path}.firstBlood"),
        submit=_required(item.get("submit"), bool, f"{path}.submit"),
        finish_judge=_required(item.get("finishJudge"), bool, f"{path}.finishJudge"),
        waiting_judge_count=_required(
            item.get("waitingJudgeCount"), int, f"{path}.waitingJudgeCount"
        ),
        submission_id=_optional_integer(item.get("submissionId"), f"{path}.submissionId"),
        score=_number(item.get("score"), f"{path}.score"),
        full_score=_number(item.get("fullScore"), f"{path}.fullScore"),
        time_consumption=_required(
            item.get("timeConsumption"), int, f"{path}.timeConsumption"
        ),
    )


def _standing(raw: Any, path: str, problem_ids: tuple[int, ...]) -> NowcoderStanding:
    item = _object(raw, path)
    raw_scores = _array(item.get("scoreList"), f"{path}.scoreList")
    scores = tuple(
        _score(raw_score, f"{path}.scoreList[{index}]")
        for index, raw_score in enumerate(raw_scores)
    )
    score_by_problem: dict[int, NowcoderProblemScore] = {}
    for score in scores:
        if score.problem_id in score_by_problem:
            raise DataValidationError(
                f"{path}.scoreList contains duplicate problemId {score.problem_id}"
            )
        score_by_problem[score.problem_id] = score
    if set(score_by_problem) != set(problem_ids):
        raise DataValidationError(
            f"{path}.scoreList problem IDs do not match problemData: "
            f"expected {list(problem_ids)}, got {list(score_by_problem)}"
        )
    raw_member_uids = item.get("teamMemberUids")
    if raw_member_uids is None and item.get("team") is False:
        raw_member_uids = []
    member_uids = tuple(
        _required(uid, int, f"{path}.teamMemberUids[{index}]")
        for index, uid in enumerate(_array(raw_member_uids, f"{path}.teamMemberUids"))
    )
    color_level = item.get("colorLevel")
    return NowcoderStanding(
        ranking=_required(item.get("ranking"), int, f"{path}.ranking"),
        uid=_required(item.get("uid"), int, f"{path}.uid"),
        user_name=_required(item.get("userName"), str, f"{path}.userName"),
        school=(
            ""
            if item.get("school") is None
            else _required(item.get("school"), str, f"{path}.school")
        ),
        team=_required(item.get("team"), bool, f"{path}.team"),
        team_member_uids=member_uids,
        accepted_count=_required(item.get("acceptedCount"), int, f"{path}.acceptedCount"),
        penalty_time_ms=_required(item.get("penaltyTime"), int, f"{path}.penaltyTime"),
        total_score=_number(item.get("totalScore"), f"{path}.totalScore"),
        full_score=_number(item.get("fullScore"), f"{path}.fullScore"),
        color_level=(
            None
            if color_level is None
            else _required(color_level, int, f"{path}.colorLevel")
        ),
        scores=tuple(score_by_problem[problem_id] for problem_id in problem_ids),
    )


def normalize_nowcoder_page(
    payload: Any, *, contest_id: int, requested_page: int
) -> NowcoderLeaderboardPage:
    path = f"Nowcoder contest {contest_id} page {requested_page}"
    root = _object(payload, path)
    if root.get("code") != 0:
        raise NowcoderError(
            f"Nowcoder business error for contest {contest_id} page {requested_page}: "
            f"code={root.get('code')!r}, message={root.get('msg')!r}"
        )
    data = _object(root.get("data"), f"{path}.data")
    basic = _object(data.get("basicInfo"), f"{path}.data.basicInfo")
    actual_contest = _required(
        basic.get("contestId"), int, f"{path}.data.basicInfo.contestId"
    )
    actual_page = _required(
        basic.get("pageCurrent"), int, f"{path}.data.basicInfo.pageCurrent"
    )
    if actual_contest != contest_id:
        raise DataValidationError(
            f"{path}.data.basicInfo.contestId is {actual_contest}, expected {contest_id}"
        )
    if actual_page != requested_page:
        raise DataValidationError(
            f"{path}.data.basicInfo.pageCurrent is {actual_page}, expected {requested_page}"
        )
    raw_problems = _array(data.get("problemData"), f"{path}.data.problemData")
    problems = tuple(
        _problem(raw_problem, f"{path}.data.problemData[{index}]")
        for index, raw_problem in enumerate(raw_problems)
    )
    problem_ids = tuple(problem.problem_id for problem in problems)
    problem_names = tuple(problem.name for problem in problems)
    if len(set(problem_ids)) != len(problem_ids):
        raise DataValidationError(f"{path}.data.problemData contains duplicate problem IDs")
    if len(set(problem_names)) != len(problem_names):
        raise DataValidationError(f"{path}.data.problemData contains duplicate problem names")
    standings = tuple(
        _standing(raw_row, f"{path}.data.rankData[{index}]", problem_ids)
        for index, raw_row in enumerate(_array(data.get("rankData"), f"{path}.data.rankData"))
    )
    return NowcoderLeaderboardPage(
        contest_id=actual_contest,
        page_current=actual_page,
        page_count=_required(
            basic.get("pageCount"), int, f"{path}.data.basicInfo.pageCount"
        ),
        page_size=_required(basic.get("pageSize"), int, f"{path}.data.basicInfo.pageSize"),
        rank_count=_required(
            basic.get("rankCount"), int, f"{path}.data.basicInfo.rankCount"
        ),
        contest_begin_time_ms=_required(
            basic.get("contestBeginTime"), int, f"{path}.data.basicInfo.contestBeginTime"
        ),
        contest_end_time_ms=_required(
            basic.get("contestEndTime"), int, f"{path}.data.basicInfo.contestEndTime"
        ),
        rank_type=_required(basic.get("rankType"), str, f"{path}.data.basicInfo.rankType"),
        is_contest_finished=_required(
            data.get("isContestFinished"), bool, f"{path}.data.isContestFinished"
        ),
        only_contest_rank_applied=_required(
            basic.get("onlyContestRankApplied"),
            bool,
            f"{path}.data.basicInfo.onlyContestRankApplied",
        ),
        problems=problems,
        standings=standings,
    )


def _page_signature(page: NowcoderLeaderboardPage) -> tuple[object, ...]:
    return (
        page.contest_id,
        page.page_count,
        page.page_size,
        page.rank_count,
        page.contest_begin_time_ms,
        page.contest_end_time_ms,
        page.rank_type,
        page.is_contest_finished,
        page.problems,
    )


def _assemble(pages: tuple[NowcoderLeaderboardPage, ...]) -> NowcoderLeaderboard:
    first = pages[0]
    if first.page_size <= 0:
        raise DataValidationError(
            f"Nowcoder contest {first.contest_id}: pageSize must be positive"
        )
    expected_pages = (
        math.ceil(first.rank_count / first.page_size) if first.rank_count else 0
    )
    if first.page_count != expected_pages:
        raise DataValidationError(
            f"Nowcoder contest {first.contest_id}: pageCount is {first.page_count}, "
            f"expected {expected_pages} for rankCount {first.rank_count}"
        )
    if len(pages) != max(1, first.page_count):
        raise DataValidationError(
            f"Nowcoder contest {first.contest_id}: fetched {len(pages)} pages, "
            f"expected {max(1, first.page_count)}"
        )
    signature = _page_signature(first)
    standings: list[NowcoderStanding] = []
    for page in pages:
        if _page_signature(page) != signature:
            raise DataValidationError(
                f"Nowcoder contest {first.contest_id} page {page.page_current}: "
                "leaderboard metadata changed during pagination"
            )
        if not page.only_contest_rank_applied:
            raise DataValidationError(
                f"Nowcoder contest {first.contest_id} page {page.page_current}: "
                "onlyContestRank was not applied"
            )
        expected_rows = min(
            first.page_size,
            max(
                0,
                first.rank_count - first.page_size * (page.page_current - 1),
            ),
        )
        if len(page.standings) != expected_rows:
            raise DataValidationError(
                f"Nowcoder contest {first.contest_id} page {page.page_current}: "
                f"has {len(page.standings)} rows, expected {expected_rows}"
            )
        standings.extend(page.standings)
    if len(standings) != first.rank_count:
        raise DataValidationError(
            f"Nowcoder contest {first.contest_id}: fetched {len(standings)} standings, "
            f"expected {first.rank_count}"
        )
    uids = [standing.uid for standing in standings]
    if len(set(uids)) != len(uids):
        raise DataValidationError(f"Nowcoder contest {first.contest_id}: duplicate standing UID")
    rankings = [standing.ranking for standing in standings]
    if any(current < previous for previous, current in zip(rankings, rankings[1:], strict=False)):
        raise DataValidationError(
            f"Nowcoder contest {first.contest_id}: source rankings are not monotonic"
        )
    return NowcoderLeaderboard(
        contest_id=first.contest_id,
        contest_begin_time_ms=first.contest_begin_time_ms,
        contest_end_time_ms=first.contest_end_time_ms,
        rank_type=first.rank_type,
        is_contest_finished=first.is_contest_finished,
        page_count=first.page_count,
        page_size=first.page_size,
        rank_count=first.rank_count,
        problems=first.problems,
        standings=tuple(standings),
    )


class NowcoderClient:
    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        client: httpx.Client | None = None,
        timeout: float = 10.0,
        attempts: int = 3,
        retry_base_delay: float = 0.25,
    ) -> None:
        if attempts < 1:
            raise ValueError("attempts must be positive")
        self.base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self.client = client or httpx.Client(timeout=timeout, follow_redirects=True)
        self.attempts = attempts
        self.retry_base_delay = retry_base_delay

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> NowcoderClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _fetch_page(
        self, contest_id: int, page: int, *, result_limit: int
    ) -> NowcoderLeaderboardPage:
        url = f"{self.base_url}/acm-heavy/acm/contest/real-time-rank-data"
        params = {
            "id": contest_id,
            "page": page,
            "limit": result_limit,
            "onlyContestRank": "true",
        }
        headers = {
            "Referer": f"{self.base_url}/acm/contest/{contest_id}",
            "User-Agent": USER_AGENT,
            "X-Requested-With": "XMLHttpRequest",
        }
        last_error: Exception | None = None
        for attempt in range(self.attempts):
            try:
                response = self.client.get(url, params=params, headers=headers)
                if response.status_code == 404:
                    raise NowcoderError(f"Nowcoder contest {contest_id} was not found")
                if response.status_code not in {408, 429} and response.status_code < 500:
                    response.raise_for_status()
                    return normalize_nowcoder_page(
                        response.json(), contest_id=contest_id, requested_page=page
                    )
                last_error = NowcoderError(
                    f"transient Nowcoder HTTP {response.status_code} "
                    f"for contest {contest_id} page {page}"
                )
            except NowcoderError:
                raise
            except (httpx.HTTPError, ValueError) as error:
                last_error = error
            if attempt + 1 < self.attempts:
                time.sleep(self.retry_base_delay * (2**attempt))
        raise NowcoderError(
            f"Nowcoder request failed for contest {contest_id} page {page}: {last_error}"
        ) from last_error

    def fetch_leaderboard(self, contest_id: int) -> NowcoderLeaderboard:
        if isinstance(contest_id, bool) or not isinstance(contest_id, int) or contest_id <= 0:
            raise ValueError("contest_id must be a positive integer")
        discovery = self._fetch_page(
            contest_id, 1, result_limit=INITIAL_RESULT_LIMIT
        )
        if discovery.rank_count < INITIAL_RESULT_LIMIT:
            first = discovery
        else:
            first = self._fetch_page(
                contest_id, 1, result_limit=MAX_RESULT_LIMIT
            )
        pages = (first,) + tuple(
            self._fetch_page(
                contest_id,
                page,
                result_limit=max(first.rank_count, INITIAL_RESULT_LIMIT),
            )
            for page in range(2, first.page_count + 1)
        )
        return _assemble(pages)


_BASE_CSV_FIELDS = (
    "contest_id",
    "ranking",
    "uid",
    "user_name",
    "school",
    "team",
    "team_member_uids",
    "accepted_count",
    "penalty_time_ms",
    "total_score",
    "full_score",
    "color_level",
)
_SCORE_CSV_FIELDS = (
    "problem_id",
    "accepted",
    "accepted_time_ms",
    "failed_count",
    "first_blood",
    "submit",
    "finish_judge",
    "waiting_judge_count",
    "submission_id",
    "score",
    "full_score",
    "time_consumption",
)


def nowcoder_csv_fieldnames(leaderboard: NowcoderLeaderboard) -> tuple[str, ...]:
    return _BASE_CSV_FIELDS + tuple(
        f"{problem.name}_{field}"
        for problem in leaderboard.problems
        for field in _SCORE_CSV_FIELDS
    )


def nowcoder_csv_rows(leaderboard: NowcoderLeaderboard) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for standing in leaderboard.standings:
        row: dict[str, object] = {
            "contest_id": leaderboard.contest_id,
            "ranking": standing.ranking,
            "uid": standing.uid,
            "user_name": standing.user_name,
            "school": standing.school,
            "team": standing.team,
            "team_member_uids": json.dumps(
                standing.team_member_uids, ensure_ascii=False, separators=(",", ":")
            ),
            "accepted_count": standing.accepted_count,
            "penalty_time_ms": standing.penalty_time_ms,
            "total_score": standing.total_score,
            "full_score": standing.full_score,
            "color_level": standing.color_level,
        }
        for problem, score in zip(leaderboard.problems, standing.scores, strict=True):
            values = {
                "problem_id": score.problem_id,
                "accepted": score.accepted,
                "accepted_time_ms": score.accepted_time_ms,
                "failed_count": score.failed_count,
                "first_blood": score.first_blood,
                "submit": score.submit,
                "finish_judge": score.finish_judge,
                "waiting_judge_count": score.waiting_judge_count,
                "submission_id": score.submission_id,
                "score": score.score,
                "full_score": score.full_score,
                "time_consumption": score.time_consumption,
            }
            row.update({f"{problem.name}_{field}": value for field, value in values.items()})
        rows.append(row)
    return tuple(rows)
