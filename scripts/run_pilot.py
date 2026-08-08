# pilots every candidate question with no tool access and keeps the ones no model can answer unaided.
# uv run -m scripts.run_pilot --dataset_path data/processed/questions.jsonl --key_path data/processed/answer_key.jsonl --output_dir results/raw/260808_pilot_v1 --seed 42

import asyncio
import json
import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import simple_parsing
from dotenv import load_dotenv
from openai import AsyncOpenAI

from src.data.io import load_jsonl, write_jsonl
from src.generation.agent import OPENROUTER_BASE_URL, run_trials
from src.generation.arms import ARMS
from src.metrics.scoring import is_match
from src.utils.config import Config
from src.utils.logging import setup_logging

LOGGER = logging.getLogger(__name__)

DEFAULT_MODELS = [
    "anthropic/claude-haiku-4.5",
    "openai/gpt-4o-mini",
    "qwen/qwen3-235b-a22b-2507",
]


@dataclass
class PilotConfig(Config):
    key_path: str = ""
    models: list[str] = field(default_factory=lambda: list(DEFAULT_MODELS))
    n_repeats: int = 5
    temperature: float = 1.0
    max_tokens: int = 2048
    max_concurrent: int = 8
    cache_dir: str = "cache"


async def run(config: PilotConfig) -> None:
    questions = load_jsonl(config.dataset_path, config.num_tasks)
    key = {record["id"]: record for record in load_jsonl(config.key_path)}
    output_dir = Path(config.output_dir)

    client = AsyncOpenAI(base_url=OPENROUTER_BASE_URL, api_key=os.environ["OPENROUTER_API_KEY"])

    records = []
    for model_id in config.models:
        model_records = await run_trials(
            client,
            model_id,
            ARMS["unaided"],
            questions,
            sandbox_dir=output_dir / "unused_sandbox",
            n_repeats=config.n_repeats,
            cache_dir=config.cache_dir,
            max_concurrent=config.max_concurrent,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
        records.extend(model_records)

    for record in records:
        if record.get("error"):
            record["correct"] = None
            continue
        gold = key[record["id"]]
        record["correct"] = is_match(record["final_answer"], gold["answer"], gold["aliases"])

    correct_by_question = defaultdict(int)
    attempts_by_question = defaultdict(int)
    for record in records:
        if record["correct"] is None:
            continue
        correct_by_question[record["id"]] += int(record["correct"])
        attempts_by_question[record["id"]] += 1

    survivors = [q for q in questions if correct_by_question[q["id"]] == 0]
    cut = [
        {
            "id": q["id"],
            "tier": q["tier"],
            "correct": correct_by_question[q["id"]],
            "attempts": attempts_by_question[q["id"]],
        }
        for q in questions
        if correct_by_question[q["id"]] > 0
    ]

    outputs_path = write_jsonl(records, output_dir / "outputs.jsonl")
    survivors_path = write_jsonl(survivors, output_dir / "survivors.jsonl")

    tier_counts = defaultdict(int)
    for q in survivors:
        tier_counts[q["tier"]] += 1

    summary = {
        "models": config.models,
        "n_repeats": config.n_repeats,
        "candidates": len(questions),
        "survivors": len(survivors),
        "cut": cut,
        "survivors_by_tier": dict(tier_counts),
        "failed_sessions": sum(1 for r in records if r.get("error")),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    print(f"outputs: {outputs_path}")
    print(f"survivors: {survivors_path} ({len(survivors)}/{len(questions)} kept)")
    print(f"survivors by tier: {dict(tier_counts)}")
    if cut:
        print(f"cut {len(cut)} answerable candidates: {[c['id'] for c in cut]}")


def main():
    load_dotenv()
    config = simple_parsing.parse(PilotConfig, add_config_path_arg=True)
    if not config.dataset_path or not config.key_path:
        raise ValueError("--dataset_path and --key_path are required, there are no default input paths")
    setup_logging(config.output_dir)
    asyncio.run(run(config))


if __name__ == "__main__":
    main()
