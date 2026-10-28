"""Fetch complete current preview sources into a new, explicitly requested cache."""
from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timezone
from pathlib import Path

import httpx

RATING_BASE = "https://hei-maom.github.io/xcpcrating/data/"
ELO_URL = "https://zzzzzzyt.github.io/xcpc-elo/data.js"
CPC_BASE = "https://cpcfinder.com/api/"


def fetch_sources(root: Path, client: httpx.Client, *, workers: int = 4) -> dict:
    """Download without falling back to old caches; record versions and hashes.

    The caller owns HTTP and output choices. Tests inject an offline transport.
    A manifest is written only after all completeness/consistency checks pass.
    """
    root.mkdir(parents=True, exist_ok=False)
    hashes = {}

    def fetch(url, path, params=None):
        response = client.get(url, params=params)
        response.raise_for_status()
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(response.content)
        return response

    def get_json(url, params=None):
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    meta = fetch(RATING_BASE + "meta.json", "xcpcrating/meta.json").json()
    board_path = "leaderboards/official/meta.json"
    board = fetch(RATING_BASE + board_path, "xcpcrating/" + board_path).json()
    if type(board["pageCount"]) is not int or board["pageCount"] < 1:
        raise ValueError("XCPC Rating: invalid page count")

    def rating_page(page):
        path = f"leaderboards/official/pages/{page}.json"
        return fetch(RATING_BASE + path, "xcpcrating/" + path).json()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        rating_pages = list(pool.map(rating_page, range(1, board["pageCount"] + 1)))
    rating_rows = [row for page in rating_pages for row in page]
    if len(rating_rows) != board["total"] or len({r[0] for r in rating_rows}) != len(rating_rows):
        raise ValueError("XCPC Rating: incomplete or duplicate leaderboard rows")
    if get_json(RATING_BASE + "meta.json") != meta or get_json(RATING_BASE + board_path) != board:
        raise ValueError("XCPC Rating changed during download; retry in a new cache")

    elo = fetch(ELO_URL, "xcpc-elo-data.js").text.strip()
    prefix = "window.__ELO_DATA__ = "
    if not elo.startswith(prefix) or not elo.endswith(";"):
        raise ValueError("XCPC Elo: invalid data assignment")
    elo_data = json.loads(elo[len(prefix):-1])
    if not elo_data["players"]:
        raise ValueError("XCPC Elo: empty player list")

    params = {"current": 1, "pageSize": 100, "sort": "rating"}
    first = fetch(CPC_BASE + "student", "cpcfinder-pages/1.json", params).json()
    pagination = first["pagination"]
    if type(pagination["pages"]) is not int or pagination["pages"] < 1:
        raise ValueError("CPC Finder: invalid page count")
    contest_params = {"current": 1, "pageSize": 100}
    contests = fetch(CPC_BASE + "contest", "cpcfinder-contests.json", contest_params).json()

    def cpc_page(page):
        document = fetch(CPC_BASE + "student", f"cpcfinder-pages/{page}.json",
                         {**params, "current": page}).json()
        expected = {**pagination, "current": page}
        if document["pagination"] != expected:
            raise ValueError("CPC Finder pagination changed during download")
        return document

    with ThreadPoolExecutor(max_workers=workers) as pool:
        pages = [first, *pool.map(cpc_page, range(2, pagination["pages"] + 1))]
    rows = [r for page in pages for r in page["data"]]
    if len(rows) != pagination["total"] or len({r["studentId"] for r in rows}) != len(rows):
        raise ValueError("CPC Finder: incomplete or duplicate student rows")
    if (get_json(CPC_BASE + "student", params) != first
            or get_json(CPC_BASE + "contest", contest_params) != contests):
        raise ValueError("CPC Finder changed during download; retry in a new cache")
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            hashes[path.relative_to(root).as_posix()] = digest
    manifest = {
        "fetchedAt": datetime.now(UTC).isoformat(),
        "sourceSnapshots": {"xcpcrating": meta["generatedAt"], "xcpcElo": elo_data["generatedAt"]},
        "counts": {"xcpcrating": len(rating_rows), "xcpcElo": len(elo_data["players"]),
                   "cpcfinder": len(rows)},
        "sha256": hashes,
    }
    (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                       encoding="utf-8")
    return manifest


def prepare_sources(args) -> None:
    """New CLI snapshots fetch live sources; historical rebuilds opt into --offline."""
    from datetime import timedelta

    names = ("xcpcrating_data", "xcpc_elo_data", "cpcfinder_pages")
    if args.offline:
        if not args.snapshot_date or any(getattr(args, name) is None for name in names):
            raise ValueError("--offline requires snapshot-date and all three cached source paths")
        return
    if any(getattr(args, name) is not None for name in names):
        raise ValueError("cached source paths require --offline; omit them for latest sources")
    now = datetime.now(timezone(timedelta(hours=8)))
    if datetime.fromisoformat(args.sort_at) <= now:
        raise ValueError("past contests require --offline and historical pre-contest sources")
    today = now.date().isoformat()
    if args.snapshot_date not in (None, today):
        raise ValueError("new snapshot date must be today; historical rebuilds require --offline")
    root = args.source_cache or Path(f"data-cache/preview-sources-{now:%Y%m%d-%H%M%S}")
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        manifest = fetch_sources(root, client)
    args.xcpcrating_data = root / "xcpcrating"
    args.xcpc_elo_data = root / "xcpc-elo-data.js"
    args.cpcfinder_pages = root / "cpcfinder-pages"
    args.snapshot_date = today
    args.cpcfinder_snapshot_date = manifest["fetchedAt"]
    args.source_fetch_manifest = manifest
