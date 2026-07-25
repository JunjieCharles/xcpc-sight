from datetime import datetime

from core import Contest
from core.seasons import (
    SEASON_2025_2026,
    SeasonSpec,
    contest_sort_key,
    select_season,
)


def make_contest(contest_id: str, title: str, series: str, start: datetime) -> Contest:
    return Contest(contest_id, title, series, start, ())


def test_invitationals_are_excluded_and_regionals_are_kept() -> None:
    regional = make_contest(
        "regional", "ICPC Asia Regional", "icpc2025", datetime(2025, 10, 1, 9)
    )
    invitational = make_contest(
        "invite", "CCPC 邀请赛", "ccpc2025", datetime(2025, 9, 1, 9)
    )
    season = select_season((regional, invitational))
    assert season.contests == (regional,)
    assert season.decisions[1].reason == "invitational excluded"


def test_default_season_explicitly_excludes_ladies_contest() -> None:
    ladies = make_contest(
        "ccpc2025ladies",
        "第十一届中国大学生程序设计竞赛（女生专场）",
        "ccpc2025",
        datetime(2025, 8, 1, 9),
    )
    season = select_season((ladies,), SEASON_2025_2026)
    assert season.contests == ()
    assert season.decisions[0].reason == "explicitly excluded"


def test_same_day_ccpc_precedes_icpc_even_when_icpc_starts_earlier() -> None:
    icpc = make_contest("i", "ICPC", "icpc2025", datetime(2025, 10, 1, 8))
    ccpc = make_contest("c", "CCPC", "ccpc2025", datetime(2025, 10, 1, 12))
    season = select_season((icpc, ccpc))
    assert [contest.contest_id for contest in season.contests] == ["c", "i"]


def test_explicit_include_and_exclude_override_title_rules() -> None:
    included = make_contest(
        "include", "Invitational", "icpc2025", datetime(2025, 10, 1)
    )
    excluded = make_contest("exclude", "Regional", "icpc2025", datetime(2025, 10, 2))
    spec = SeasonSpec(
        "custom",
        ("icpc2025",),
        include_ids=frozenset({"include"}),
        exclude_ids=frozenset({"exclude"}),
    )
    assert select_season((included, excluded), spec).contests == (included,)


def test_sort_key_accepts_aware_and_naive_times() -> None:
    aware = make_contest(
        "aware", "Aware", "icpc2025", datetime.fromisoformat("2025-10-01T00:00:00+00:00")
    )
    naive = make_contest("naive", "Naive", "icpc2025", datetime(2025, 10, 1, 9))
    assert contest_sort_key(aware) < contest_sort_key(naive)
