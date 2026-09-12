"""Offline first-preliminary aggregation experiment; requires the dev dependencies."""

import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.stats import rankdata, spearmanr
from sklearn.model_selection import GroupKFold

ROOT = Path(__file__).resolve().parents[1]


def aggregate(values, method, parameter=400):
    values = np.asarray(values, dtype=float)
    highest = values.max()
    if method == "max":
        return highest
    if method == "mean":
        return values.mean()
    if method == "blend":
        return parameter * highest + (1 - parameter) * values.mean()
    if method in {"lse", "sum_lse"}:
        total = np.exp((values - highest) * np.log(10) / parameter).sum()
        divisor = len(values) if method == "lse" else 1
        return highest + parameter * np.log10(total / divisor)
    raise ValueError(method)


def rho(scores, actual):
    return float(spearmanr(scores, -np.asarray(actual)).statistic)


def top_recall(scores, actual, k=100):
    """Fractional membership at the prediction cutoff; actual rank <= k is the target."""
    scores, actual = np.asarray(scores), np.asarray(actual)
    cutoff = np.sort(scores)[-min(k, len(scores))]
    above, tied = scores > cutoff, scores == cutoff
    weights = above.astype(float) + tied * (min(k, len(scores)) - above.sum()) / tied.sum()
    target = actual <= k
    return float(weights[target].sum() / target.sum()) if target.any() else None


def paired_school_bootstrap(scores, baseline, actual, groups, repetitions=500):
    rng = np.random.default_rng(20260912)
    indices = [np.flatnonzero(groups == group) for group in np.unique(groups)]
    differences = []
    for _ in range(repetitions):
        sample = np.concatenate([indices[i] for i in rng.integers(len(indices), size=len(indices))])
        differences.append(
            rho(scores[sample], actual[sample]) - rho(baseline[sample], actual[sample])
        )
    return np.quantile(differences, [0.025, 0.975]).tolist()


def main():
    paths = [
        ROOT / "static/data/previews/2026-2027.json",
        ROOT / "static/data/reviews/2026-2027.json",
    ]
    preview, review = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    contest = next(c for c in review["contests"] if c["previewId"] == preview["id"])
    results = {t["previewTeamId"]: t for t in contest["teams"] if t["hasActivity"]}
    assert len(results) == 2496
    output = {
        "inputs": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths
        },
        "sources": {},
    }
    specs = {
        "max": ("max", 0),
        "mean": ("mean", 0),
        "blend75": ("blend", 0.75),
        "lse400": ("lse", 400),
        "sum_lse400": ("sum_lse", 400),
    }
    specs.update({f"lse{scale}": ("lse", scale) for scale in [50, 100, 200, 800, 1600]})
    specs.update({f"blend{int(w * 100)}": ("blend", w) for w in [0.25, 0.5, 0.9]})
    for source in [s["id"] for s in preview["metricSources"]]:
        rows = []
        for team in preview["teams"]:
            values = [
                m["ratings"][source] for m in team["members"] if m["ratings"][source] is not None
            ]
            if team["id"] in results and values:
                assert max(values) == team["ratings"][source]
                rows.append((team, values, results[team["id"]]["actualRank"]))
        actual = np.array([r[2] for r in rows])
        groups = np.array([r[0]["school"] for r in rows])
        counts = np.array([len(r[1]) for r in rows])
        predictions = {
            key: np.array([aggregate(r[1], *spec) for r in rows]) for key, spec in specs.items()
        }
        detail = {
            "n": len(rows),
            "schools": len(set(groups)),
            "known_counts": {str(n): int((counts == n).sum()) for n in [1, 2, 3]},
            "methods": {},
        }
        for key, scores in predictions.items():
            record = {
                "rho": rho(scores, actual),
                "rank_mae": float(np.mean(abs(rankdata(-scores) - rankdata(actual)))),
                "recall100": top_recall(scores, actual),
                "recall300": top_recall(scores, actual, 300),
            }
            if key in ["max", "lse400", "mean", "blend75", "sum_lse400"]:
                record["delta_rho_school_bootstrap95"] = paired_school_bootstrap(
                    scores, predictions["max"], actual, groups
                )
            detail["methods"][key] = record
        detail["subgroups"] = {}
        masks = {
            "three_known": counts == 3,
            "two_known": counts == 2,
            "one_known": counts == 1,
            "actual_top300": actual <= 300,
        }
        masks["three_known_unequal"] = (counts == 3) & np.array(
            [max(r[1]) != min(r[1]) for r in rows]
        )
        for label, mask in masks.items():
            detail["subgroups"][label] = {
                "n": int(mask.sum()),
                **{key: rho(scores[mask], actual[mask]) for key, scores in predictions.items()},
            }
        detail["group_cv"] = []
        for train, test in GroupKFold(5).split(actual, groups=groups):
            candidates = [k for k in specs if k != "sum_lse400"]
            best = max(candidates, key=lambda k: rho(predictions[k][train], actual[train]))
            detail["group_cv"].append(
                {
                    "n": len(test),
                    "selected": best,
                    **{
                        k: rho(predictions[k][test], actual[test])
                        for k in ["max", "lse400", "blend75", "mean"]
                    },
                    "tuned": rho(predictions[best][test], actual[test]),
                }
            )
        output["sources"][source] = detail
    target = ROOT / "doc/experiments/team-aggregation-first-preliminary.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
