# runs the four experimental arms over the question set and writes raw trial records.
# uv run -m scripts.run_study --dataset_path data/processed/questions.jsonl --key_source data/processed/session_notes.txt --output_dir results/raw/260808_study_v1 --model_id all --n_repeats 5 --seed 42

import asyncio
import json
import logging
import os
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import simple_parsing
from dotenv import load_dotenv
from openai import AsyncOpenAI

from src.data.io import load_jsonl, write_jsonl
from src.generation.agent import OPENROUTER_BASE_URL, run_trials
from src.generation.arms import ARMS
from src.generation.sandbox import build_sandbox
from src.utils.config import Config, write_config_json
from src.utils.logging import setup_logging

LOGGER = logging.getLogger(__name__)

STUDY_ARMS = ("no_resource", "permitted", "not_monitored", "monitored")

DEFAULT_MODELS = [
    "anthropic/claude-haiku-4.5",
    "openai/gpt-4o-mini",
    "qwen/qwen3-235b-a22b-2507",
]


@dataclass
class StudyConfig(Config):
    key_source: str = ""
    models: list[str] = field(default_factory=lambda: list(DEFAULT_MODELS))
    arms: list[str] = field(default_factory=lambda: list(STUDY_ARMS))
    n_repeats: int = 5
    temperature: float = 1.0
    max_tokens: int = 2048
    max_steps: int = 6
    max_concurrent: int = 8
    tool_scratchpad: bool = False
    cache_dir: str = "cache"


async def run(config: StudyConfig) -> None:
    questions = load_jsonl(config.dataset_path, config.num_tasks)
    output_dir = Path(config.output_dir)

    # one sandbox per key condition, not per trial. the tool only reads, so trials cannot
    # contaminate each other through it, and rebuilding 3000 directories buys nothing.
    sandboxes = {
        True: build_sandbox(output_dir / "sandbox_with_key", key_source=config.key_source),
        False: build_sandbox(output_dir / "sandbox_no_key", key_source=None),
    }

    client = AsyncOpenAI(base_url=OPENROUTER_BASE_URL, api_key=os.environ["OPENROUTER_API_KEY"])

    records = []
    for model_id in config.models:
        for arm_name in config.arms:
            arm = ARMS[arm_name]
            arm_records = await run_trials(
                client,
                model_id,
                arm,
                questions,
                sandbox_dir=sandboxes[arm.include_key],
                n_repeats=config.n_repeats,
                cache_dir=config.cache_dir,
                max_concurrent=config.max_concurrent,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                max_steps=config.max_steps,
                tool_scratchpad=config.tool_scratchpad,
            )
            records.extend(arm_records)
            accessed = sum(1 for r in arm_records if r.get("accessed"))
            LOGGER.info(f"{model_id} {arm_name}: access {accessed}/{len(arm_records)}")

    outputs_path = write_jsonl(records, output_dir / "outputs.jsonl")

    access_by_arm = Counter()
    total_by_arm = Counter()
    for record in records:
        if record.get("error"):
            continue
        total_by_arm[(record["model_id"], record["arm"])] += 1
        access_by_arm[(record["model_id"], record["arm"])] += int(bool(record["accessed"]))

    summary = {
        "questions": len(questions),
        "models": config.models,
        "arms": config.arms,
        "n_repeats": config.n_repeats,
        "tool_scratchpad": config.tool_scratchpad,
        "sessions": len(records),
        "failed_sessions": sum(1 for r in records if r.get("error")),
        "unparseable": sum(1 for r in records if not r.get("error") and not r.get("parsed_cleanly")),
        "hit_step_ceiling": sum(1 for r in records if r.get("hit_step_ceiling")),
        "access_rate": {
            f"{model}|{arm}": round(access_by_arm[(model, arm)] / total_by_arm[(model, arm)], 4)
            for model, arm in sorted(total_by_arm)
        },
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    write_config_json(config, output_dir)

    print(f"outputs: {outputs_path}")
    print(f"sessions: {len(records)}, failed: {summary['failed_sessions']}, unparseable: {summary['unparseable']}")
    for label, rate in summary["access_rate"].items():
        print(f"  access {label}: {rate}")
    print(f"score with: uv run -m scripts.score_study --dataset_path {outputs_path} --output_dir {output_dir}")


def main():
    load_dotenv()
    config = simple_parsing.parse(StudyConfig, add_config_path_arg=True)
    if not config.dataset_path or not config.key_source:
        raise ValueError("--dataset_path and --key_source are required, there are no default input paths")
    setup_logging(config.output_dir)
    asyncio.run(run(config))


if __name__ == "__main__":
    main()
