from dataclasses import replace
from datetime import datetime

import pytest

from core import Contest, DefaultNormalizer, TeamResult
from scripts.school_ranking import rank_key, school_standings


def team(school, member, penalty, **kwargs):
    return TeamResult(member, member, school, (member,), 999, 1, penalty, **kwargs)


def contest(name, *teams):
    return Contest(name, name, "icpc2026", datetime(2026, 9, 6), tuple(teams))


def test_school_best_aliases_ties_and_activity_filtering():
    c = contest("one", team("A", "a", 10), team("Old A", "b", 11),
                team("B", "c", 10), team("C", "d", 30),
                team("Star", "e", 0, official=False),
                team("Absent", "f", 0, has_activity=False),
                replace(team("Zero", "g", 0), solved=0))
    rows = school_standings((c,), DefaultNormalizer(school_aliases={"Old A": "A"}))
    assert [(r.school, r.ranks, r.rank) for r in rows] == [
        ("Old A", (1,), 1), ("B", (1,), 1), ("C", (3,), 3), ("Zero", (4,), 4),
    ]
    assert [t.ranks for t in rows[0].teams] == [(1,), (3,)]


def test_best_second_third_and_missing_results():
    assert rank_key((1, 80, 90)) < rank_key((2, 2, 2))
    assert rank_key((5, 1, 9)) < rank_key((1, 6, 7))
    assert rank_key((5, 1, 8)) < rank_key((1, 9, 5))
    assert rank_key((1, 5, 999)) < rank_key((None, 1, 5))
    assert rank_key((1, 5, 8)) == rank_key((8, 1, 5))


def test_three_contest_overall_ties_keep_original_order_of_ranks():
    a, b, c = team("A", "a", 10), team("B", "b", 20), team("C", "c", 30)
    one = contest("one", a, b, c)
    two = contest("two", replace(a, penalty=20), replace(b, penalty=10), c)
    three = contest("three", replace(a, penalty=10), replace(b, penalty=10), c)
    rows = school_standings((one, two, three), DefaultNormalizer())
    assert [(r.school, r.rank, r.ranks) for r in rows] == [
        ("A", 1, (1, 2, 1)), ("B", 1, (2, 1, 1)), ("C", 3, (3, 3, 3)),
    ]


def test_histories_require_same_school_and_complete_roster_not_team_name():
    first = replace(team("A", "a", 10), team_name="Old", members=("a", "b"))
    renamed = replace(first, team_name="New", members=("B", "Ａ"))
    changed = replace(first, team_name="New", members=("a", "c"))
    other_school = replace(first, school_name="B")
    rows = school_standings((contest("one", first), contest("two", renamed),
                             contest("three", changed, other_school)), DefaultNormalizer())
    assert [(t.name, t.ranks) for t in rows[0].teams] == [
        ("New", (1, 1, None)), ("New", (None, None, 1)),
    ]
    assert rows[1].teams[0].ranks == (None, None, 1)


def test_top100_includes_non_school_best_and_fallback_unions():
    leaders = [team(f"School{i}", f"p{i}", i) for i in range(1, 99)]
    a = team("A", "a", 99)
    b = team("A", "b", 100)
    c = team("A", "c", 101)
    d = team("D", "d", 102)
    e = team("D", "e", 103)
    one = contest("one", *leaders, a, b, c, d, e)
    two = contest("two", *leaders, a, b, c, replace(d, penalty=103),
                  replace(e, penalty=102))
    rows = {r.school: r for r in school_standings((one, two), DefaultNormalizer())}
    assert [t.name for t in rows["A"].teams] == ["a", "b"]
    assert {t.name for t in rows["D"].teams} == {"d", "e"}
    assert rows["D"].ranks == (100, 100)


def test_empty_rosters_are_not_joined_and_contest_ids_must_be_unique():
    t = replace(team("A", "a", 10), members=())
    one, two = contest("one", t), contest("two", t)
    rows = school_standings((one, two), DefaultNormalizer())
    assert len(rows[0].teams) == 2
    with pytest.raises(ValueError, match="unique IDs"):
        school_standings((one, one), DefaultNormalizer())
