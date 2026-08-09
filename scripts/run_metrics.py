# runs the pre-registered analysis over the scored trial records from every study cell.
# uv run -m scripts.run_metrics --results_dirs results/raw/260809_study_plain_core results/raw/260809_study_plain_deepseek --output_dir results/raw/260809_analysis --seed 42

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import simple_parsing

from src.data.io import load_jsonl
from src.metrics.analysis import (
    cell_rates,
    disclosure_given_read,
    fit_mixed_logistic,
    manipulation_summary,
    paired_arm_difference,
    scratchpad_distribution,
)
from src.utils.config import Config, write_config_json
from src.utils.logging import setup_logging

LOGGER = logging.getLogger(__name__)


@dataclass
class MetricsConfig(Config):
    results_dirs: list[str] = field(default_factory=list)
    consistent_only: bool = True  # restrict the H2 contrast to trials where the belief took hold


def load_frame(results_dirs: list[str]) -> pd.DataFrame:
    """Load every cell's scored records, tagging each with the prompt level from its directory."""
    records = []
    for directory in results_dirs:
        path = Path(directory) / "scored.jsonl"
        if not path.exists():
            raise FileNotFoundError(f"{path} missing. run scripts.score_study on {directory} first")
        level = "instructed" if "instructed" in Path(directory).name else "plain"
        for record in load_jsonl(path):
            record["level"] = level
            records.append(record)
    frame = pd.DataFrame(records)
    frame = frame[frame["error"].isna()] if "error" in frame else frame
    LOGGER.info("loaded %d scored trials from %d cells", len(frame), len(results_dirs))
    return frame


def main():
    config = simple_parsing.parse(MetricsConfig, add_config_path_arg=True)
    if not config.results_dirs:
        raise ValueError("--results_dirs is required, there is no default input path")
    setup_logging(config.output_dir)
    output_dir = Path(config.output_dir)

    frame = load_frame(config.results_dirs)

    h2_frame = frame
    if config.consistent_only:
        # the not_monitored vs monitored contrast is only interpretable where the stated belief
        # matched the arm. control arms make no monitoring claim and are never filtered.
        mask = ~frame["arm"].isin(["not_monitored", "monitored"]) | (frame["manipulation"] == "consistent")
        h2_frame = frame[mask]
        LOGGER.info("H2 contrast restricted to %d of %d trials", len(h2_frame), len(frame))

    contrasts = []
    models = []
    for (level, model), group in h2_frame.groupby(["level", "model_id"], sort=True):
        for arm_a, arm_b in [
            ("not_monitored", "monitored"),
            ("not_monitored", "permitted"),
            ("monitored", "permitted"),
        ]:
            result = paired_arm_difference(group, arm_a, arm_b)
            contrasts.append({"level": level, "model_id": model, **result})
        models.append({"level": level, "model_id": model, **fit_mixed_logistic(group)})

    analysis = {
        "trials": int(len(frame)),
        "trials_in_h2_contrast": int(len(h2_frame)),
        "consistent_only": config.consistent_only,
        "access_rates": cell_rates(frame, "accessed"),
        "read_rates": cell_rates(frame, "read_forbidden"),
        "answer_match_rates": cell_rates(frame, "answer_match"),
        "paired_contrasts": contrasts,
        "mixed_logistic": models,
        "disclosure_given_read": disclosure_given_read(frame),
        "scratchpad_distribution": scratchpad_distribution(frame),
        "manipulation_check": manipulation_summary(frame),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = output_dir / "analysis.json"
    metrics_path.write_text(json.dumps(analysis, indent=2))
    write_config_json(config, output_dir)

    print(f"analysis: {metrics_path}")
    print("access rate by cell")
    for row in analysis["access_rates"]:
        model = row["model_id"].split("/")[-1]
        print(
            f"  {row['level']:10s} {model:22s} {row['arm']:14s} {row['rate']} [{row['ci_low']}, {row['ci_high']}] n={row['n']}"
        )
    print("paired contrast, not_monitored minus monitored")
    for row in contrasts:
        if row["comparison"] != "not_monitored-monitored":
            continue
        model = row["model_id"].split("/")[-1]
        print(
            f"  {row['level']:10s} {model:22s} diff={row['mean_difference']} ci=[{row.get('ci_low')}, {row.get('ci_high')}] p={row.get('p_value')}"
        )


if __name__ == "__main__":
    main()
