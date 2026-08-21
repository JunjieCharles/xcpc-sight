import numpy as np
import pandas as pd

from problem_rating.experiment_models import ensemble_predictions, prepare_features


def test_sample_gated_model_uses_shallow_tree_for_sparse_times():
    predictions = {
        "gaussian + prev1-3 / HistGBR": np.array([1000.0, 2000.0, 3000.0]),
        "gaussian + prev1-3 / Shallow GBR": np.array([1100.0, 2100.0, 3100.0]),
    }

    ensembles = ensemble_predictions(predictions, np.array([0, 19, 20]))

    assert np.array_equal(
        ensembles["sample-gated HistGBR / Shallow GBR"],
        np.array([1100.0, 2100.0, 3000.0]),
    )


def test_problem_order_is_excluded_from_every_model_feature_family():
    data = pd.DataFrame(
        [
            {
                "participantCount": 100,
                "contestDurationSeconds": 7200,
                "problemOrder": 7,
            }
        ]
    )

    _, families = prepare_features(data)

    assert all("problemOrder" not in columns for columns in families.values())
    assert all("ratedProblemCount" in columns for columns in families.values())
