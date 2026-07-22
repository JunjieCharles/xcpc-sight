from __future__ import annotations

import hashlib
import time
from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any
from urllib.parse import quote

import httpx

from .errors import DataValidationError, RankLandError
from .models import Contest, ContestProvenance, TeamResult

JsonObject = dict[str, Any]


def _object(value: Any, path: str) -> JsonObject:
    if not isinstance(value, dict):
        raise DataValidationError(f"{path} must be an object")
    return value


def _array(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise DataValidationError(f"{path} must be an array")
    return value


def _text(value: Any, fallback: str = "") -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if not isinstance(value, dict):
        return fallback
    texts = value.get("texts") if isinstance(value.get("texts"), dict) else {}
    for candidate in (
        value.get("zh-CN"),
        texts.get("zh-CN"),
        value.get("fallback"),
        texts.get("en"),
        value.get("en"),
    ):
        if isinstance(candidate, str) and candidate:
            return candidate
    return fallback


def _integer(value: Any, fallback: int = 0) -> int:
    if isinstance(value, bool):
        return fallback
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            pass
    return fallback


def _boolean(value: Any, fallback: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value in (1, "1", "true", "True"):
        return True
    if value in (0, "0", "false", "False"):
        return False
    return fallback


def _minutes(value: Any) -> int:
    if not isinstance(value, list) or not value:
        return 0
    amount = max(0, _integer(value[0]))
    unit = _text(value[1] if len(value) > 1 else "min", "min").casefold()
    if unit in {"ms", "millisecond", "milliseconds"}:
        return amount // 60_000
    if unit in {"s", "sec", "second", "seconds"}:
        return amount // 60
    if unit in {"h", "hour", "hours"}:
        return amount * 60
    return amount


def _parse_datetime(value: Any, path: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise DataValidationError(f"{path} must be an ISO-8601 string")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise DataValidationError(f"{path} is not a valid ISO-8601 datetime") from error


def _unwrap(payload: Any, endpoint: str) -> Any:
    root = _object(payload, endpoint)
    if root.get("success") is not True or root.get("code") != 0:
        raise RankLandError(
            f"RankLand business error at {endpoint}: code={root.get('code')!r}, "
            f"message={root.get('msg')!r}"
        )
    if "data" not in root:
        raise DataValidationError(f"{endpoint}.data is missing")
    return root["data"]


def _collection_children(node: Mapping[str, Any]) -> list[Any]:
    children = node.get("children")
    return children if isinstance(children, list) else []


def _find_collection_node(content: Any, collection_id: str) -> JsonObject:
    content_root = _object(content, "collection.data.content")
    root = _object(content_root.get("root"), "collection.data.content.root")
    wanted = collection_id.casefold()
    stack = [root]
    while stack:
        node = stack.pop()
        keys = (
            _text(node.get("uniqueKey")).casefold(),
            _text(node.get("name")).casefold(),
        )
        if any(key == wanted or key == f"dir-{wanted}" for key in keys):
            return node
        stack.extend(
            child for child in _collection_children(node) if isinstance(child, dict)
        )
    raise DataValidationError(f"official collection does not contain {collection_id!r}")


def _leaf_contest_ids(node: Mapping[str, Any]) -> tuple[str, ...]:
    result: list[str] = []
    stack: list[Mapping[str, Any]] = [node]
    while stack:
        current = stack.pop()
        children = _collection_children(current)
        if not children:
            key = _text(current.get("uniqueKey"))
            if key and not key.startswith("dir-"):
                result.append(key)
            continue
        stack.extend(reversed([child for child in children if isinstance(child, dict)]))
    return tuple(dict.fromkeys(result))


def _member_names(user: Mapping[str, Any], path: str) -> tuple[str, ...]:
    members = user.get("teamMembers", [])
    if members is None:
        return ()
    members = _array(members, f"{path}.teamMembers")
    names: list[str] = []
    for index, raw_member in enumerate(members):
        member = _object(raw_member, f"{path}.teamMembers[{index}]")
        name = _text(member.get("name")).strip()
        if not name:
            continue
        if len(members) == 1 and len(name.split()) >= 3:
            names.extend(name.split())
        else:
            names.append(name)
    return tuple(names[:3])


def _team_drafts(payload: Any, contest_uk: str) -> tuple[str, datetime, list[dict[str, Any]]]:
    root = _object(payload, f"contest {contest_uk} SRK root")
    contest = _object(root.get("contest", {}), f"contest {contest_uk}.contest")
    title = _text(contest.get("title"), contest_uk)
    start_at = _parse_datetime(contest.get("startAt"), f"contest {contest_uk}.contest.startAt")
    rows = _array(root.get("rows"), f"contest {contest_uk}.rows")
    drafts: list[dict[str, Any]] = []
    for index, raw_row in enumerate(rows):
        path = f"contest {contest_uk}.rows[{index}]"
        row = _object(raw_row, path)
        user = _object(row.get("user", {}), f"{path}.user")
        score = _object(row.get("score", {}), f"{path}.score")
        statuses = row.get("statuses", [])
        statuses = _array(statuses, f"{path}.statuses") if statuses is not None else []
        has_activity = False
        for status_index, raw_status in enumerate(statuses):
            status = _object(raw_status, f"{path}.statuses[{status_index}]")
            result = status.get("result")
            if result is not None and (_integer(status.get("tries")) > 0 or result in {"AC", "FB"}):
                has_activity = True
        solved = max(0, _integer(score.get("value")))
        drafts.append(
            {
                "source_index": index,
                "team_id": _text(user.get("id"), str(index)),
                "team_name": _text(user.get("name"), f"Team {index + 1}"),
                "school_name": _text(user.get("organization")),
                "members": _member_names(user, f"{path}.user"),
                "explicit_rank": _integer(row.get("rank"), 0),
                "solved": solved,
                "penalty": _minutes(score.get("time")),
                "official": _boolean(user.get("official"), False),
                "has_activity": has_activity or solved > 0,
            }
        )
    return title, start_at, drafts


def normalize_srk_contest(
    payload: Any,
    *,
    contest_uk: str,
    series: str,
    provenance: ContestProvenance | None = None,
    metadata_start_at: datetime | None = None,
    metadata_title: str | None = None,
) -> Contest:
    title, start_at, drafts = _team_drafts(payload, contest_uk)
    official = [draft for draft in drafts if draft["official"]]
    explicit_ranks = [draft["explicit_rank"] for draft in official]
    use_explicit = bool(official) and all(rank > 0 for rank in explicit_ranks)
    if not use_explicit:
        ordered = sorted(
            official,
            key=lambda item: (-item["solved"], item["penalty"], item["source_index"]),
        )
        previous_score: tuple[int, int] | None = None
        current_rank = 0
        for position, draft in enumerate(ordered, start=1):
            score = (draft["solved"], draft["penalty"])
            if score != previous_score:
                current_rank = position
                previous_score = score
            draft["explicit_rank"] = current_rank

    teams = tuple(
        TeamResult(
            team_id=draft["team_id"],
            team_name=draft["team_name"],
            school_name=draft["school_name"],
            members=draft["members"],
            rank=draft["explicit_rank"] if draft["official"] else 0,
            solved=draft["solved"],
            penalty=draft["penalty"],
            official=draft["official"],
            has_activity=draft["has_activity"],
        )
        for draft in drafts
    )
    return Contest(
        contest_id=contest_uk,
        title=metadata_title or title,
        series=series,
        start_at=metadata_start_at or start_at,
        teams=teams,
        provenance=provenance,
    )


class RankLandClient:
    def __init__(
        self,
        *,
        base_url: str = "https://rl.algoux.cn/api/v2",
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

    def __enter__(self) -> RankLandClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _get_json(self, url: str, *, envelope: bool = True) -> Any:
        last_error: Exception | None = None
        for attempt in range(self.attempts):
            try:
                response = self.client.get(url)
                if response.status_code == 404:
                    raise RankLandError(f"RankLand resource not found: {url}")
                if response.status_code not in {408, 429} and response.status_code < 500:
                    response.raise_for_status()
                    payload = response.json()
                    return _unwrap(payload, url) if envelope else payload
                last_error = RankLandError(
                    f"transient RankLand HTTP {response.status_code} at {url}"
                )
            except (httpx.HTTPError, ValueError) as error:
                last_error = error
            if attempt + 1 < self.attempts:
                time.sleep(self.retry_base_delay * (2**attempt))
        raise RankLandError(f"RankLand request failed at {url}: {last_error}") from last_error

    def collection_contest_ids(self, collection_id: str) -> tuple[str, ...]:
        content = self._get_json(f"{self.base_url}/public/collections/official")
        return _leaf_contest_ids(_find_collection_node(content.get("content"), collection_id))

    def fetch_contest(self, contest_uk: str, *, series: str) -> Contest:
        encoded_uk = quote(contest_uk, safe="")
        detail_url = f"{self.base_url}/public/contests/{encoded_uk}"
        detail = _object(self._get_json(detail_url), f"contest {contest_uk} detail")
        file_id = _text(detail.get("srkFileID"))
        if not file_id:
            raise DataValidationError(f"contest {contest_uk} has no srkFileID")
        file_url = f"{self.base_url}/public/files/{quote(file_id, safe='')}"
        file_data = _object(self._get_json(file_url), f"contest {contest_uk} file")
        cdn_url = _text(file_data.get("url"))
        if not cdn_url:
            raise DataValidationError(f"contest {contest_uk} file metadata has no URL")
        srk = self._get_json(cdn_url, envelope=False)
        content_hash = hashlib.sha256(
            httpx.Response(200, json=srk).content
        ).hexdigest()
        provenance = ContestProvenance(
            contest_uk=contest_uk,
            file_id=file_id,
            file_url=cdn_url,
            sha256=_text(file_data.get("hashValue"), content_hash),
        )
        metadata_start = detail.get("startAt")
        return normalize_srk_contest(
            srk,
            contest_uk=contest_uk,
            series=series,
            provenance=provenance,
            metadata_start_at=(
                _parse_datetime(metadata_start, f"contest {contest_uk}.startAt")
                if metadata_start
                else None
            ),
            metadata_title=_text(detail.get("title"), _text(detail.get("name"))) or None,
        )

    def fetch_collection(self, collection_id: str) -> tuple[Contest, ...]:
        return tuple(
            self.fetch_contest(contest_id, series=collection_id)
            for contest_id in self.collection_contest_ids(collection_id)
        )

    def fetch_collections(self, collection_ids: Iterable[str]) -> tuple[Contest, ...]:
        return tuple(
            contest
            for collection_id in collection_ids
            for contest in self.fetch_collection(collection_id)
        )
