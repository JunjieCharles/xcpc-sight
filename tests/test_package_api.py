def test_packages_export_their_public_apis() -> None:
    import core
    import problem_rating
    import rating

    assert core.Contest.__module__ == "core.models"
    assert core.RankLandClient.__module__ == "core.rankland"
    assert core.NowcoderClient.__module__ == "core.nowcoder"
    assert core.nowcoder_leaderboard_to_contest.__module__ == "core.nowcoder"
    assert core.NowcoderError.__module__ == "core.errors"
    assert core.HduClient.__module__ == "core.hdu"
    assert core.HduError.__module__ == "core.errors"
    assert core.hdu_leaderboard_to_contest.__module__ == "core.hdu"
    assert core.rebuild_competition_ranks.__module__ == "core.ranking"
    assert rating.RatingConfig.__module__ == "rating.models"
    assert rating.calculate_series_ratings.__module__ == "rating.calculation"
    assert rating.project_series_rating_data.__module__ == "rating.static_data"
    assert rating.project_static_data_index.__module__ == "rating.static_data"
    assert problem_rating.ProblemRatingRecord.__module__ == "problem_rating.static_data"
    assert (
        problem_rating.project_problem_rating_series.__module__
        == "problem_rating.static_data"
    )
