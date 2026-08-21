from problem_rating.predict_xcpc import (
    parse_hdu_accepted_time,
    stable_competitor_id,
)


def test_parse_hdu_accepted_time_ignores_failed_only_cells():
    assert parse_hdu_accepted_time("00:03:07") == 187
    assert parse_hdu_accepted_time("02:24:26 (-3)") == 8666
    assert parse_hdu_accepted_time("(-14)") is None
    assert parse_hdu_accepted_time("") is None


def test_stable_competitor_id_keeps_sources_separate():
    nowcoder = stable_competitor_id("nowcoder", "standing:123")
    hdu = stable_competitor_id("hdu", "standing:123")

    assert nowcoder.startswith("c_")
    assert len(nowcoder) == 66
    assert hdu != nowcoder
