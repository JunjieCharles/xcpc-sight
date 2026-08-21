"""Compare interpretable problem-rating models on problem-level features."""

from __future__ import annotations

import argparse
import math
import re
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import RidgeCV
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import SplineTransformer, StandardScaler

from .build_problem_features import DEFAULT_OUTPUT


warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    module=r"sklearn\..*",
)


@dataclass(frozen=True)
class Evaluation:
    name: str
    sample_count: int
    mae: float
    rmse: float
    within_200: float
    bias: float


def prepare_features(data: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    """Create transformed feature families discovered from the CSV schema."""

    features = data.copy()
    solve_logits = sorted(
        [column for column in features if re.fullmatch(r"solveLogitR\d+", column)],
        key=lambda column: int(column.removeprefix("solveLogitR")),
    )
    participant_counts = sorted(
        [
            column
            for column in features
            if re.fullmatch(r"participantCountR\d+", column)
        ],
        key=lambda column: int(column.removeprefix("participantCountR")),
    )
    log_participant_counts = []
    for column in participant_counts:
        transformed_column = f"log{column[0].upper()}{column[1:]}"
        features[transformed_column] = np.log1p(features[column])
        log_participant_counts.append(transformed_column)

    features["logParticipantCount"] = np.log1p(features["participantCount"])
    features["logContestDuration"] = np.log(features["contestDurationSeconds"])

    metadata = [
        "problemOrder",
        "ratedProblemCount",
        "logContestDuration",
        "teamSizeMedian",
        "burstUnder60Rate",
        "burstUnder120Rate",
    ]
    time_prev1 = [
        "logTimePrev1Median",
        "logTimePrev1Iqr",
        "hasPrev1Rate",
        "solverRatingMedian",
        "solverRatingIqr",
    ]
    time_prev123 = [
        "logTimePrev1Median",
        "logTimePrev1Iqr",
        "hasPrev1Rate",
        "logTimePrev2Median",
        "logTimePrev2Iqr",
        "hasPrev2Rate",
        "logTimePrev3Median",
        "logTimePrev3Iqr",
        "hasPrev3Rate",
        "solverRatingMedian",
        "solverRatingIqr",
    ]
    solve_curve = solve_logits + log_participant_counts + ["logParticipantCount"]
    families = {
        "time prev1": time_prev1 + metadata,
        "time prev1-3": time_prev123 + metadata,
        "solve curve": solve_curve + metadata,
        "combined prev1": solve_curve + time_prev1 + metadata,
        "combined prev1-3": solve_curve + time_prev123 + metadata,
    }
    return features, families


def build_models():
    alphas = np.logspace(-3, 4, 20)
    return {
        "Ridge": make_pipeline(
            SimpleImputer(strategy="median", add_indicator=True),
            StandardScaler(),
            RidgeCV(alphas=alphas),
        ),
        "GAM": make_pipeline(
            SimpleImputer(strategy="median", add_indicator=True),
            SplineTransformer(n_knots=4, degree=2, include_bias=False),
            StandardScaler(),
            RidgeCV(alphas=alphas),
        ),
        "Shallow GBR": make_pipeline(
            SimpleImputer(strategy="median", add_indicator=True),
            GradientBoostingRegressor(
                n_estimators=200,
                learning_rate=0.03,
                max_depth=2,
                min_samples_leaf=8,
                loss="huber",
                random_state=42,
            ),
        ),
    }


def calculate_evaluation(name: str, actual, predicted) -> Evaluation:
    actual_values = np.asarray(actual, dtype=float)
    predicted_values = np.asarray(predicted, dtype=float)
    errors = predicted_values - actual_values
    return Evaluation(
        name=name,
        sample_count=len(actual_values),
        mae=float(mean_absolute_error(actual_values, predicted_values)),
        rmse=float(math.sqrt(mean_squared_error(actual_values, predicted_values))),
        within_200=float(np.mean(np.abs(errors) <= 200)),
        bias=float(np.mean(errors)),
    )


def grouped_predictions(
    data: pd.DataFrame,
    feature_columns: list[str],
    estimator,
    *,
    folds: int,
) -> np.ndarray:
    predictions = np.full(len(data), np.nan)
    splitter = GroupKFold(n_splits=folds)
    for train_indices, test_indices in splitter.split(
        data, data["problemRating"], groups=data["contestId"]
    ):
        model = clone(estimator)
        model.fit(
            data.iloc[train_indices][feature_columns],
            data.iloc[train_indices]["problemRating"],
        )
        predictions[test_indices] = model.predict(
            data.iloc[test_indices][feature_columns]
        )
    return predictions


def chronological_predictions(
    data: pd.DataFrame,
    feature_columns: list[str],
    estimator,
    *,
    holdout_contests: int,
) -> tuple[np.ndarray, np.ndarray]:
    contest_starts = (
        data.groupby("contestId")["contestStartTimeSeconds"].first().sort_values()
    )
    test_contests = set(contest_starts.tail(holdout_contests).index)
    train_mask = ~data["contestId"].isin(test_contests)
    test_mask = ~train_mask
    model = clone(estimator)
    model.fit(data.loc[train_mask, feature_columns], data.loc[train_mask, "problemRating"])
    return test_mask.to_numpy(), model.predict(data.loc[test_mask, feature_columns])


def print_evaluation(evaluation: Evaluation):
    print(
        f"{evaluation.name:<34} "
        f"n={evaluation.sample_count:>3} "
        f"MAE={evaluation.mae:>6.1f} "
        f"RMSE={evaluation.rmse:>6.1f} "
        f"<=200={evaluation.within_200:>6.1%} "
        f"bias={evaluation.bias:>6.1f}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Compare problem-rating models with contest-level holdouts."
    )
    parser.add_argument("--features", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--holdout-contests", type=int, default=20)
    args = parser.parse_args()

    data = pd.read_csv(args.features)
    if data["contestId"].nunique() < args.folds:
        raise ValueError("not enough contests for the requested grouped folds")
    if data["contestId"].nunique() <= args.holdout_contests:
        raise ValueError("chronological holdout must leave training contests")

    prepared, feature_families = prepare_features(data)
    models = build_models()
    comparisons = [
        ("time prev1", "GAM"),
        ("time prev1-3", "GAM"),
        ("solve curve", "Ridge"),
        ("solve curve", "GAM"),
        ("combined prev1", "GAM"),
        ("combined prev1-3", "GAM"),
        ("combined prev1-3", "Shallow GBR"),
    ]

    print("\nContest-grouped cross-validation")
    for family_name, model_name in comparisons:
        predictions = grouped_predictions(
            prepared,
            feature_families[family_name],
            models[model_name],
            folds=args.folds,
        )
        print_evaluation(
            calculate_evaluation(
                f"{family_name} / {model_name}",
                prepared["problemRating"],
                predictions,
            )
        )

    print(f"\nChronological holdout: newest {args.holdout_contests} contests")
    for family_name, model_name in comparisons:
        test_mask, predictions = chronological_predictions(
            prepared,
            feature_families[family_name],
            models[model_name],
            holdout_contests=args.holdout_contests,
        )
        print_evaluation(
            calculate_evaluation(
                f"{family_name} / {model_name}",
                prepared.loc[test_mask, "problemRating"],
                predictions,
            )
        )


if __name__ == "__main__":
    main()
