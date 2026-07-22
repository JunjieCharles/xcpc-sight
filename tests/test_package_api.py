def test_core_and_rating_export_their_public_apis() -> None:
    import core
    import rating

    assert core.Contest.__module__ == "core.models"
    assert core.RankLandClient.__module__ == "core.rankland"
    assert rating.RatingConfig.__module__ == "rating.models"
    assert rating.calculate_series_ratings.__module__ == "rating.calculation"
