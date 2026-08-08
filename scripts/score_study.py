# scores DV 2, DV 3, DV 4 and the manipulation check over trial records from run_study.
# uv run -m scripts.score_study --dataset_path results/raw/260808_study_v1/outputs.jsonl --key_path data/processed/answer_key.jsonl --output_dir results/raw/260808_study_v1 --seed 42

import asyncio
import json
import logging
import os
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import simple_parsing
from dotenv import load_dotenv
from openai import AsyncOpenAI

from src.data.io import load_jsonl, write_jsonl
from src.generation.agent import OPENROUTER_BASE_URL
from src.metrics.rubrics import score_records
from src.metrics.scoring import is_match
from src.utils.config import Config
from src.utils.logging import setup_logging

LOGGER = logging.getLogger(__name__)

# a judge that is also a subject would be scoring its own responses, so the judge sits outside
# the model lineup entirely.
DEFAULT_JUDGE = "google/gemini-2.5-flash-lite"


@dataclass
class ScoreConfig(Config):
    key_path: str = ""
    judge_model: str = DEFAULT_JUDGE
    max_concurrent: int = 8
    cache_dir: str = "cache"


async def run(config: ScoreConfig) -> None:
    records = load_jsonl(config.dataset_path, config.num_tasks)
    key = {r["id"]: r for r in load_jsonl(config.key_path)}
    output_dir = Path(config.output_dir)

    for record in records:
        if record.get("error"):
            record["answer_match"] = None
            continue
        gold = key[record["id"]]
        record["answer_match"] = is_match(record["final_answer"], gold["answer"], gold["aliases"])

    client = AsyncOpenAI(base_url=OPENROUTER_BASE_URL, api_key=os.environ["OPENROUTER_API_KEY"])
    records = await score_records(client, config.judge_model, records, config.cache_dir, config.max_concurrent)

    scored_path = write_jsonl(records, output_dir / "scored.jsonl")

    by_arm = defaultdict(Counter)
    accessed_by_arm = defaultdict(Counter)
    for record in records:
        if record.get("error"):
            continue
        cell = (record["model_id"], record["arm"])
        by_arm[cell]["n"] += 1
        by_arm[cell]["accessed"] += int(bool(record["accessed"]))
        by_arm[cell]["answer_match"] += int(bool(record["answer_match"]))
        by_arm[cell][f"scratchpad_{record['scratchpad_category']}"] += 1
        by_arm[cell][f"manipulation_{record['manipulation']}"] += 1
        if record["accessed"]:
            accessed_by_arm[cell][f"disclosure_{record['disclosure']}"] += 1

    summary = {
        "judge_model": config.judge_model,
        "cells": {
            f"{model}|{arm}": {
                **dict(by_arm[(model, arm)]),
                "disclosure_given_access": dict(accessed_by_arm[(model, arm)]),
            }
            for model, arm in sorted(by_arm)
        },
        "unjudged": sum(1 for r in records if not r.get("error") and r.get("scratchpad_category") is None),
    }
    (output_dir / "metrics.json").write_text(json.dumps(summary, indent=2))

    print(f"scored: {scored_path}")
    print(f"metrics: {output_dir / 'metrics.json'}")
    for cell, counts in summary["cells"].items():
        n = counts["n"]
        print(f"  {cell}: access {counts['accessed']}/{n}, answer_match {counts['answer_match']}/{n}")


def main():
    load_dotenv()
    config = simple_parsing.parse(ScoreConfig, add_config_path_arg=True)
    if not config.dataset_path or not config.key_path:
        raise ValueError("--dataset_path and --key_path are required, there are no default input paths")
    setup_logging(config.output_dir)
    asyncio.run(run(config))


if __name__ == "__main__":
    main()
