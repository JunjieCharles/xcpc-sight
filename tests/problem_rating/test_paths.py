from problem_rating.paths import (
    ANALYSIS_DIR,
    API_CACHE_DIR,
    LOCAL_DATA_DIR,
    PROCESSED_DATA_DIR,
    PROJECT_ROOT,
)


def test_problem_rating_local_data_is_isolated_from_participant_rating_cache() -> None:
    expected_root = PROJECT_ROOT / "data-cache" / "problem-rating"

    assert expected_root == LOCAL_DATA_DIR
    assert expected_root / "data" / "raw" / "api_cache" == API_CACHE_DIR
    assert expected_root / "data" / "processed" == PROCESSED_DATA_DIR
    assert expected_root / "outputs" / "analysis" == ANALYSIS_DIR
