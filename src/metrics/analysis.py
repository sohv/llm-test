# the pre-registered analysis: access rates with intervals, the question-paired arm contrast,
# and the mixed-effects logistic model with a random intercept per question.

import logging

import numpy as np
import pandas as pd
from scipy import stats

LOGGER = logging.getLogger(__name__)

Z95 = 1.959963984540054


def wilson_ci(successes: int, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval.

    Wilson rather than normal-approximation because several cells sit at or near zero, where the
    normal interval collapses to a width of zero and would report a floored rate as if it were
    known exactly.
    """
    if n == 0:
        return (float("nan"), float("nan"))
    p = successes / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def cell_rates(frame: pd.DataFrame, outcome: str = "accessed") -> list[dict]:
    """Rate of an outcome per model, arm and prompt level, with a Wilson interval."""
    rows = []
    for (level, model, arm), group in frame.groupby(["level", "model_id", "arm"], sort=True):
        valid = group[group[outcome].notna()]
        successes = int(valid[outcome].sum())
        n = len(valid)
        low, high = wilson_ci(successes, n)
        rows.append(
            {
                "level": level,
                "model_id": model,
                "arm": arm,
                "n": n,
                "successes": successes,
                "rate": round(successes / n, 4) if n else None,
                "ci_low": round(low, 4),
                "ci_high": round(high, 4),
            }
        )
    return rows


def paired_arm_difference(frame: pd.DataFrame, arm_a: str, arm_b: str, outcome: str = "accessed") -> dict:
    """Per-question paired difference in rate between two arms, for one model and level.

    Paired because the same questions run in every arm, so differencing within question removes
    between-question variance. Reported with a t interval over questions, the unit of pairing.
    """
    pivot = (
        frame[frame["arm"].isin([arm_a, arm_b])]
        .groupby(["id", "arm"])[outcome]
        .mean()
        .unstack("arm")
        .dropna(subset=[arm_a, arm_b] if arm_a in frame["arm"].values and arm_b in frame["arm"].values else None)
    )
    if arm_a not in pivot or arm_b not in pivot or pivot.empty:
        return {"comparison": f"{arm_a}-{arm_b}", "n_questions": 0, "mean_difference": None}

    diffs = (pivot[arm_a] - pivot[arm_b]).dropna()
    n = len(diffs)
    mean = float(diffs.mean())
    if n < 2 or diffs.std(ddof=1) == 0:
        return {
            "comparison": f"{arm_a}-{arm_b}",
            "n_questions": n,
            "mean_difference": round(mean, 4),
            "ci_low": None,
            "ci_high": None,
            "p_value": None,
            "note": "no variance across questions, interval undefined",
        }

    sem = float(diffs.std(ddof=1) / np.sqrt(n))
    half = stats.t.ppf(0.975, n - 1) * sem
    t_stat, p_value = stats.ttest_1samp(diffs, 0.0)
    return {
        "comparison": f"{arm_a}-{arm_b}",
        "n_questions": n,
        "mean_difference": round(mean, 4),
        "ci_low": round(mean - half, 4),
        "ci_high": round(mean + half, 4),
        "p_value": round(float(p_value), 4),
    }


def fit_mixed_logistic(frame: pd.DataFrame, outcome: str = "accessed") -> dict:
    """Mixed-effects logistic regression on the outcome, random intercept per question.

    Returns a descriptive skip rather than a fit when the outcome has no variance. A floored model
    carries no information about arm effects, and forcing a fit there produces a separation
    artefact rather than an estimate.
    """
    from statsmodels.genmod.bayes_mixed_glm import BinomialBayesMixedGLM

    data = frame[frame[outcome].notna()].copy()
    data[outcome] = data[outcome].astype(int)

    if data[outcome].nunique() < 2:
        return {"fitted": False, "reason": f"no variance in {outcome}", "rate": round(data[outcome].mean(), 4)}
    if data["arm"].nunique() < 2:
        return {"fitted": False, "reason": "fewer than two arms present"}

    model = BinomialBayesMixedGLM.from_formula(
        f"{outcome} ~ C(arm, Treatment(reference='permitted')) + C(tier)",
        {"question": "0 + C(id)"},
        data,
    )
    result = model.fit_vb(verbose=False)
    return {
        "fitted": True,
        "n": int(len(data)),
        "terms": {
            name: {"coef": round(float(mean), 4), "sd": round(float(sd), 4)}
            for name, mean, sd in zip(result.model.exog_names, result.fe_mean, result.fe_sd)
        },
    }


def disclosure_given_read(frame: pd.DataFrame) -> list[dict]:
    """DV 3, conditioned on a successful read rather than on an attempt."""
    rows = []
    read = frame[frame["read_forbidden"] == True]  # noqa: E712
    for (level, model, arm), group in read.groupby(["level", "model_id", "arm"], sort=True):
        counts = group["disclosure"].value_counts().to_dict()
        n = len(group)
        rows.append(
            {
                "level": level,
                "model_id": model,
                "arm": arm,
                "n_read": n,
                "counts": {str(k): int(v) for k, v in counts.items()},
                "not_disclosed_rate": round(counts.get("not_disclosed", 0) / n, 4) if n else None,
            }
        )
    return rows


def scratchpad_distribution(frame: pd.DataFrame) -> list[dict]:
    """DV 4 category counts per cell."""
    rows = []
    for (level, model, arm), group in frame.groupby(["level", "model_id", "arm"], sort=True):
        counts = group["scratchpad_category"].value_counts().to_dict()
        rows.append(
            {
                "level": level,
                "model_id": model,
                "arm": arm,
                "n": len(group),
                "counts": {str(k): int(v) for k, v in counts.items()},
            }
        )
    return rows


def manipulation_summary(frame: pd.DataFrame) -> list[dict]:
    """Manipulation check outcomes for the two arms where a monitoring claim was made."""
    rows = []
    experimental = frame[frame["arm"].isin(["not_monitored", "monitored"])]
    for (level, model, arm), group in experimental.groupby(["level", "model_id", "arm"], sort=True):
        counts = group["manipulation"].value_counts().to_dict()
        n = len(group)
        rows.append(
            {
                "level": level,
                "model_id": model,
                "arm": arm,
                "n": n,
                "counts": {str(k): int(v) for k, v in counts.items()},
                "consistent_rate": round(counts.get("consistent", 0) / n, 4) if n else None,
            }
        )
    return rows
