# builds questions.jsonl, answer_key.jsonl, and the forbidden session_notes.txt from the candidate pool.
# uv run -m scripts.build_questions --candidates_path data/raw/question_candidates.yaml --output_dir data/processed

import logging
from dataclasses import dataclass
from pathlib import Path

import simple_parsing

from src.data.io import load_jsonl, write_jsonl
from src.data.questions import load_candidates, render_answer_key, select_balanced, split_key
from src.utils.config import Config

LOGGER = logging.getLogger(__name__)


@dataclass
class BuildConfig(Config):
    candidates_path: str = ""
    keep_ids_path: str = ""  # pilot survivors jsonl; empty means keep the whole pool
    per_tier: int = 0  # questions kept per tier after the pilot cut; 0 means keep every survivor


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    config = simple_parsing.parse(BuildConfig, add_config_path_arg=True)
    if not config.candidates_path:
        raise ValueError("--candidates_path is required, there is no default input path")

    questions = load_candidates(config.candidates_path)

    if config.keep_ids_path:
        keep = {r["id"] for r in load_jsonl(config.keep_ids_path)}
        questions = [q for q in questions if q["id"] in keep]
        LOGGER.info("filtered to %d surviving questions", len(questions))

    if config.per_tier:
        questions = select_balanced(questions, config.per_tier)
        LOGGER.info("selected %d questions, %d per tier", len(questions), config.per_tier)

    prompts, key = split_key(questions)
    output_dir = Path(config.output_dir)

    questions_path = write_jsonl(prompts, output_dir / "questions.jsonl")
    key_path = write_jsonl(key, output_dir / "answer_key.jsonl")

    notes_path = output_dir / "session_notes.txt"
    notes_path.write_text(render_answer_key(key, questions))

    print(f"questions: {questions_path}")
    print(f"answer key: {key_path}")
    print(f"forbidden file: {notes_path}")


if __name__ == "__main__":
    main()
