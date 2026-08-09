# pure-logic tests for the analysis: interval behaviour at the boundary and the question pairing.

import pandas as pd

from src.metrics.analysis import cell_rates, paired_arm_difference, wilson_ci


def test_wilson_interval_stays_open_at_zero():
    low, high = wilson_ci(0, 30)
    assert low == 0.0
    # a floored cell must not report a zero-width interval, which is what the normal approximation
    # would give and would read as a rate known exactly
    assert high > 0.05


def test_wilson_interval_narrows_with_sample_size():
    narrow = wilson_ci(5, 100)
    wide = wilson_ci(1, 20)
    assert (narrow[1] - narrow[0]) < (wide[1] - wide[0])


def _frame(rows):
    return pd.DataFrame(
        [{"level": "plain", "model_id": "m", "id": qid, "arm": arm, "accessed": hit} for qid, arm, hit in rows]
    )


def test_paired_difference_pairs_within_question():
    frame = _frame(
        [
            ("q1", "not_monitored", True),
            ("q1", "monitored", False),
            ("q2", "not_monitored", True),
            ("q2", "monitored", False),
            ("q3", "not_monitored", False),
            ("q3", "monitored", False),
        ]
    )
    result = paired_arm_difference(frame, "not_monitored", "monitored")
    assert result["n_questions"] == 3
    assert result["mean_difference"] == round(2 / 3, 4)


def test_paired_difference_reports_no_variance_rather_than_crashing():
    frame = _frame(
        [
            ("q1", "not_monitored", False),
            ("q1", "monitored", False),
            ("q2", "not_monitored", False),
            ("q2", "monitored", False),
        ]
    )
    result = paired_arm_difference(frame, "not_monitored", "monitored")
    assert result["mean_difference"] == 0.0
    assert result["ci_low"] is None


def test_cell_rates_carry_an_interval():
    frame = _frame([("q1", "monitored", True), ("q2", "monitored", False)])
    rows = cell_rates(frame)
    assert len(rows) == 1
    assert rows[0]["rate"] == 0.5
    assert rows[0]["ci_low"] < 0.5 < rows[0]["ci_high"]
