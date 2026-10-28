import argparse
import json

import httpx
import pytest

from scripts.preview_sources import CPC_BASE, ELO_URL, RATING_BASE, fetch_sources, prepare_sources


def transport(*, duplicate=False, changing=False):
    meta_calls = 0

    def handler(request):
        nonlocal meta_calls
        url = str(request.url).split("?")[0]
        if url == RATING_BASE + "meta.json":
            meta_calls += 1
            return httpx.Response(200, json={"generatedAt": str(meta_calls if changing else 1)})
        if url == RATING_BASE + "leaderboards/official/meta.json":
            data = {"pageCount": 2, "total": 2}
        elif "leaderboards/official/pages/" in url:
            page = int(url.rsplit("/", 1)[1].split(".")[0])
            data = [[1 if duplicate else page, "A", "School", 1400]]
        elif url == ELO_URL:
            return httpx.Response(200, text='window.__ELO_DATA__ = '
                                  '{"generatedAt":"v1","players":[{}]};')
        elif url == CPC_BASE + "student":
            page = int(request.url.params["current"])
            data = {"pagination": {"current": page, "pages": 2, "total": 2, "pageSize": 100},
                    "data": [{"studentId": str(page)}]}
        elif url == CPC_BASE + "contest":
            data = {"data": [{"contestId": 80, "dataStatus": "OK"}]}
        else:
            raise AssertionError(url)
        return httpx.Response(200, json=data)
    return httpx.MockTransport(handler)


def test_complete_download_records_versions_and_hashes(tmp_path):
    with httpx.Client(transport=transport()) as client:
        root = tmp_path / "new"
        manifest = fetch_sources(root, client, workers=1)
        assert manifest["counts"] == {"xcpcrating": 2, "xcpcElo": 1, "cpcfinder": 2}
        assert len(manifest["sha256"]) == 8
        assert json.loads((root / "manifest.json").read_text("utf-8")) == manifest
        with pytest.raises(FileExistsError):
            fetch_sources(root, client)


@pytest.mark.parametrize("option", ["duplicate", "changing"])
def test_incomplete_or_changing_sources_do_not_get_success_manifest(tmp_path, option):
    with httpx.Client(transport=transport(**{option: True})) as client:
        root = tmp_path / "bad"
        with pytest.raises(ValueError):
            fetch_sources(root, client, workers=1)
        assert not (root / "manifest.json").exists()


def test_fresh_generation_cannot_silently_reuse_cached_paths():
    args = argparse.Namespace(offline=False, xcpcrating_data="old", xcpc_elo_data="old",
                              cpcfinder_pages="old", snapshot_date="2026-09-04")
    with pytest.raises(ValueError, match="cached source paths require --offline"):
        prepare_sources(args)
    args.offline = True
    prepare_sources(args)
    args.xcpc_elo_data = None
    with pytest.raises(ValueError, match="all three cached source paths"):
        prepare_sources(args)


def test_new_generation_downloads_and_stamps_sources(tmp_path, monkeypatch):
    from scripts import preview_sources

    seen = []
    manifest = {"fetchedAt": "2026-10-28T00:00:00+00:00"}
    monkeypatch.setattr(preview_sources, "fetch_sources",
                        lambda root, client: seen.append(root) or manifest)
    args = argparse.Namespace(offline=False, xcpcrating_data=None, xcpc_elo_data=None,
                              cpcfinder_pages=None, snapshot_date=None,
                              source_cache=tmp_path / "fresh", sort_at="2999-01-01T00:00:00+08:00")
    prepare_sources(args)
    assert seen == [tmp_path / "fresh"]
    assert args.xcpcrating_data == tmp_path / "fresh/xcpcrating"
    assert args.cpcfinder_pages == tmp_path / "fresh/cpcfinder-pages"
    assert args.cpcfinder_snapshot_date == manifest["fetchedAt"]
    assert args.source_fetch_manifest == manifest


def test_past_contests_cannot_be_regenerated_with_live_sources(tmp_path):
    args = argparse.Namespace(offline=False, xcpcrating_data=None, xcpc_elo_data=None,
                              cpcfinder_pages=None, snapshot_date=None,
                              source_cache=tmp_path / "fresh", sort_at="2000-01-01T00:00:00+08:00")
    with pytest.raises(ValueError, match="past contests require --offline"):
        prepare_sources(args)
    assert not (tmp_path / "fresh").exists()
