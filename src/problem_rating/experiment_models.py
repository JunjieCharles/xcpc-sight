"""Compare interpretable problem-rating models on problem-level features."""

from __future__ import annotations

import argparse
import math
import re
import time
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import (
    GradientBoostingRegressor,
    HistGradientBoostingRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import GridSearchCV, GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import SplineTransformer, StandardScaler
from sklearn.svm import SVR

try:
    from catboost import CatBoostRegressor
except ImportError:  # pragma: no cover - depends on the optional experiment package
    CatBoostRegressor = None

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

    def centered_columns(prefix: str) -> list[str]:
        return sorted(
            [column for column in features if re.fullmatch(rf"{re.escape(prefix)}\d+", column)],
            key=lambda column: int(column.removeprefix(prefix)),
        )

    def log_count_columns(columns: list[str]) -> list[str]:
        transformed = []
        for column in columns:
            transformed_column = f"log{column[0].upper()}{column[1:]}"
            features[transformed_column] = np.log1p(features[column])
            transformed.append(transformed_column)
        return transformed

    solve_logits = centered_columns("solveLogitR")
    participant_counts = centered_columns("participantCountR")
    triangle_logits = centered_columns("triangleSolveLogitR")
    triangle_counts = centered_columns("triangleEffectiveCountR")
    gaussian_logits = centered_columns("gaussianSolveLogitR")
    gaussian_counts = centered_columns("gaussianEffectiveCountR")
    log_participant_counts = log_count_columns(participant_counts)
    log_triangle_counts = log_count_columns(triangle_counts)
    log_gaussian_counts = log_count_columns(gaussian_counts)

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

    def every_second_center(columns: list[str]) -> list[str]:
        return [
            column
            for column in columns
            if (int(re.search(r"\d+$", column).group()) - 800) % 200 == 0
        ]

    box_curve = solve_logits + log_participant_counts + ["logParticipantCount"]
    box_curve_200 = (
        every_second_center(solve_logits)
        + every_second_center(log_participant_counts)
        + ["logParticipantCount"]
    )
    triangle_curve = triangle_logits + log_triangle_counts + ["logParticipantCount"]
    gaussian_curve = gaussian_logits + log_gaussian_counts + ["logParticipantCount"]
    irt_curve = [
        "irtRating50",
        "irtSlope",
        "irtIntercept",
        "logParticipantCount",
    ]
    families = {
        "time prev1": time_prev1 + metadata,
        "time prev1-3": time_prev123 + metadata,
        "box curve 100": box_curve + metadata,
        "box curve 200": box_curve_200 + metadata,
        "triangle curve": triangle_curve + metadata,
        "gaussian curve": gaussian_curve + metadata,
        "IRT curve": irt_curve + metadata,
        "box + prev1": box_curve + time_prev1 + metadata,
        "triangle + prev1": triangle_curve + time_prev1 + metadata,
        "gaussian + prev1": gaussian_curve + time_prev1 + metadata,
        "IRT + prev1": irt_curve + time_prev1 + metadata,
        "gaussian + prev1-3": gaussian_curve + time_prev123 + metadata,
    }
    return features, families


def build_models():
    alphas = np.logspace(-2, 4, 9)

    def ridge_search(*, spline_knots: int | None = None):
        steps = [
            SimpleImputer(strategy="median", add_indicator=True),
        ]
        if spline_knots is not None:
            steps.append(
                SplineTransformer(
                    n_knots=spline_knots,
                    degree=2,
                    include_bias=False,
                )
            )
        steps.extend([StandardScaler(), Ridge()])
        return GridSearchCV(
            make_pipeline(*steps),
            param_grid={"ridge__alpha": alphas},
            scoring="neg_mean_absolute_error",
            cv=GroupKFold(n_splits=4),
        )

    models = {
        "Ridge": ridge_search(),
        "GAM-3": ridge_search(spline_knots=3),
        "GAM-4": ridge_search(spline_knots=4),
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
        "RBF-SVR": GridSearchCV(
            make_pipeline(
                SimpleImputer(strategy="median", add_indicator=True),
                StandardScaler(),
                SVR(kernel="rbf"),
            ),
            param_grid={
                "svr__C": [100.0, 300.0, 1000.0],
                "svr__epsilon": [25.0, 75.0],
                "svr__gamma": ["scale"],
            },
            scoring="neg_mean_absolute_error",
            cv=GroupKFold(n_splits=4),
            n_jobs=1,
        ),
        "HistGBR": make_pipeline(
            SimpleImputer(strategy="median", add_indicator=True),
            HistGradientBoostingRegressor(
                loss="absolute_error",
                learning_rate=0.05,
                max_iter=250,
                max_leaf_nodes=15,
                min_samples_leaf=15,
                l2_regularization=5.0,
                early_stopping=False,
                random_state=42,
            ),
        ),
    }
    if CatBoostRegressor is not None:
        models["CatBoost"] = CatBoostRegressor(
            iterations=400,
            learning_rate=0.04,
            depth=5,
            l2_leaf_reg=5.0,
            loss_function="MAE",
            verbose=False,
            allow_writing_files=False,
            random_seed=42,
            thread_count=-1,
        )
    return models


def fit_with_groups(estimator, features, target, groups):
    """Fit grid searches with contest groups and ordinary models normally."""

    if isinstance(estimator, GridSearchCV):
        return estimator.fit(features, target, groups=groups)
    return estimator.fit(features, target)


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
        fit_with_groups(
            model,
            data.iloc[train_indices][feature_columns],
            data.iloc[train_indices]["problemRating"],
            data.iloc[train_indices]["contestId"],
        )
        predictions[test_indices] = model.predict(data.iloc[test_indices][feature_columns])
    return predictions


def chronological_predictions(
    data: pd.DataFrame,
    feature_columns: list[str],
    estimator,
    *,
    holdout_contests: int,
) -> tuple[np.ndarray, np.ndarray]:
    contest_starts = data.groupby("contestId")["contestStartTimeSeconds"].first().sort_values()
    test_contests = set(contest_starts.tail(holdout_contests).index)
    train_mask = ~data["contestId"].isin(test_contests)
    test_mask = ~train_mask
    model = clone(estimator)
    fit_with_groups(
        model,
        data.loc[train_mask, feature_columns],
        data.loc[train_mask, "problemRating"],
        data.loc[train_mask, "contestId"],
    )
    return test_mask.to_numpy(), model.predict(data.loc[test_mask, feature_columns])


def print_evaluation(
    evaluation: Evaluation,
    *,
    elapsed_seconds: float | None = None,
):
    elapsed = "" if elapsed_seconds is None else f" time={elapsed_seconds:>6.1f}s"
    print(
        f"{evaluation.name:<34} "
        f"n={evaluation.sample_count:>3} "
        f"MAE={evaluation.mae:>6.1f} "
        f"RMSE={evaluation.rmse:>6.1f} "
        f"<=200={evaluation.within_200:>6.1%} "
        f"bias={evaluation.bias:>6.1f}"
        f"{elapsed}"
    )


def ensemble_predictions(
    predictions_by_name: dict[str, np.ndarray],
    time_sample_counts: np.ndarray,
) -> dict[str, np.ndarray]:
    """Build fixed-weight ensembles without learning from held-out targets."""

    preferred_models = [
        "gaussian + prev1 / GAM-3",
        "gaussian + prev1-3 / Shallow GBR",
        "gaussian + prev1-3 / RBF-SVR",
        "gaussian + prev1-3 / HistGBR",
        "gaussian + prev1-3 / CatBoost",
    ]
    available = [
        predictions_by_name[name] for name in preferred_models if name in predictions_by_name
    ]
    ensembles = {}
    if len(available) >= 2:
        stacked = np.vstack(available)
        ensembles.update(
            {
                "advanced fixed mean ensemble": np.mean(stacked, axis=0),
                "advanced fixed median ensemble": np.median(stacked, axis=0),
            }
        )

    hist_name = "gaussian + prev1-3 / HistGBR"
    shallow_name = "gaussian + prev1-3 / Shallow GBR"
    if hist_name in predictions_by_name and shallow_name in predictions_by_name:
        gated = predictions_by_name[hist_name].copy()
        sparse_mask = np.asarray(time_sample_counts) < 20
        gated[sparse_mask] = predictions_by_name[shallow_name][sparse_mask]
        ensembles["sample-gated HistGBR / Shallow GBR"] = gated
    return ensembles


def print_sparse_slices(
    data: pd.DataFrame,
    mask: np.ndarray,
    predictions: np.ndarray,
    *,
    model_name: str,
):
    """Report the slices most likely to hide weak sparse-problem behaviour."""

    held_out = data.loc[mask].reset_index(drop=True)
    slices = {
        "rating <= 1200": held_out["problemRating"] <= 1200,
        "rating 1300-2200": held_out["problemRating"].between(1300, 2200),
        "rating >= 2300": held_out["problemRating"] >= 2300,
        "time samples = 0": held_out["timeSampleCount"] == 0,
        "time samples 1-19": held_out["timeSampleCount"].between(1, 19),
        "time samples >= 100": held_out["timeSampleCount"] >= 100,
    }
    print(f"\nChronological sparse slices for {model_name}")
    for slice_name, slice_mask in slices.items():
        if not slice_mask.any():
            continue
        print_evaluation(
            calculate_evaluation(
                slice_name,
                held_out.loc[slice_mask, "problemRating"],
                predictions[slice_mask.to_numpy()],
            )
        )


def main():
    parser = argparse.ArgumentParser(
        description="Compare problem-rating models with contest-level holdouts."
    )
    parser.add_argument("--features", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--holdout-contests", type=int, default=20)
    parser.add_argument(
        "--suite",
        choices=["baseline", "advanced", "all"],
        default="all",
        help="select the model comparison suite",
    )
    args = parser.parse_args()

    data = pd.read_csv(args.features)
    if data["contestId"].nunique() < args.folds:
        raise ValueError("not enough contests for the requested grouped folds")
    if data["contestId"].nunique() <= args.holdout_contests:
        raise ValueError("chronological holdout must leave training contests")

    prepared, feature_families = prepare_features(data)
    models = build_models()
    baseline_comparisons = [
        ("time prev1", "GAM-3"),
        ("box curve 100", "GAM-3"),
        ("box curve 100", "GAM-4"),
        ("box curve 200", "GAM-3"),
        ("triangle curve", "GAM-3"),
        ("gaussian curve", "GAM-3"),
        ("IRT curve", "Ridge"),
        ("IRT curve", "GAM-3"),
        ("box + prev1", "GAM-3"),
        ("triangle + prev1", "GAM-3"),
        ("gaussian + prev1", "GAM-3"),
        ("IRT + prev1", "GAM-3"),
        ("gaussian + prev1-3", "Shallow GBR"),
    ]
    advanced_comparisons = [
        ("gaussian + prev1", "GAM-3"),
        ("gaussian + prev1-3", "Shallow GBR"),
        ("gaussian + prev1-3", "RBF-SVR"),
        ("gaussian + prev1-3", "HistGBR"),
        ("gaussian + prev1-3", "CatBoost"),
    ]
    if args.suite == "baseline":
        comparisons = baseline_comparisons
    elif args.suite == "advanced":
        comparisons = advanced_comparisons
    else:
        comparisons = baseline_comparisons + advanced_comparisons
    comparisons = list(dict.fromkeys(comparisons))
    unavailable = [(family, model) for family, model in comparisons if model not in models]
    for family_name, model_name in unavailable:
        print(f"Skipping {family_name} / {model_name}: optional dependency missing")
    comparisons = [item for item in comparisons if item not in unavailable]

    print("\nContest-grouped cross-validation")
    grouped_results = {}
    for family_name, model_name in comparisons:
        started_at = time.perf_counter()
        predictions = grouped_predictions(
            prepared,
            feature_families[family_name],
            models[model_name],
            folds=args.folds,
        )
        label = f"{family_name} / {model_name}"
        grouped_results[label] = predictions
        print_evaluation(
            calculate_evaluation(
                label,
                prepared["problemRating"],
                predictions,
            ),
            elapsed_seconds=time.perf_counter() - started_at,
        )
    grouped_ensembles = ensemble_predictions(
        grouped_results,
        prepared["timeSampleCount"].to_numpy(),
    )
    grouped_results.update(grouped_ensembles)
    for label, predictions in grouped_ensembles.items():
        print_evaluation(calculate_evaluation(label, prepared["problemRating"], predictions))

    print(f"\nChronological holdout: newest {args.holdout_contests} contests")
    chronological_results = {}
    chronological_mask = None
    for family_name, model_name in comparisons:
        started_at = time.perf_counter()
        test_mask, predictions = chronological_predictions(
            prepared,
            feature_families[family_name],
            models[model_name],
            holdout_contests=args.holdout_contests,
        )
        label = f"{family_name} / {model_name}"
        chronological_mask = test_mask
        chronological_results[label] = predictions
        print_evaluation(
            calculate_evaluation(
                label,
                prepared.loc[test_mask, "problemRating"],
                predictions,
            ),
            elapsed_seconds=time.perf_counter() - started_at,
        )
    chronological_ensembles = ensemble_predictions(
        chronological_results,
        prepared.loc[chronological_mask, "timeSampleCount"].to_numpy(),
    )
    chronological_results.update(chronological_ensembles)
    for label, predictions in chronological_ensembles.items():
        print_evaluation(
            calculate_evaluation(
                label,
                prepared.loc[chronological_mask, "problemRating"],
                predictions,
            )
        )

    if chronological_results:
        actual = prepared.loc[chronological_mask, "problemRating"]
        best_name, best_predictions = min(
            chronological_results.items(),
            key=lambda item: mean_absolute_error(actual, item[1]),
        )
        print_sparse_slices(
            prepared,
            chronological_mask,
            best_predictions,
            model_name=best_name,
        )


if __name__ == "__main__":
    main()
