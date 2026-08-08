import hashlib
import json
import logging
from pathlib import Path

LOGGER = logging.getLogger(__name__)


def trial_cache_path(
    cache_dir: Path | str, model: str, arm: str, question_id: str, trial_index: int, prompt: str
) -> Path:
    """Cache path for one whole trial.

    Keyed on the trial coordinates, not on the message list. Repeats of a question within an arm
    send identical messages, so a message-keyed cache would return one response N times and every
    access rate would come out at exactly 0.0 or 1.0. The system prompt is folded in so editing an
    arm's wording invalidates that arm rather than silently serving stale trials.
    """
    salt = f"{model}|{arm}|{question_id}|{trial_index}|{hashlib.md5(prompt.encode()).hexdigest()}"
    directory = Path(cache_dir) / "trials"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{hashlib.md5(salt.encode()).hexdigest()}.json"


def judgment_cache_path(cache_dir: Path | str, judge_model: str, rubric_name: str, rubric: str, text: str) -> Path:
    """Cache path for one rubric judgment.

    Keyed on the text being judged rather than on trial coordinates, so re-scoring a run costs
    nothing and two identical responses are judged once.
    """
    salt = f"{judge_model}|{rubric_name}|{hashlib.md5(rubric.encode()).hexdigest()}|{text}"
    directory = Path(cache_dir) / "judgments"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{hashlib.md5(salt.encode()).hexdigest()}.json"


def load_cached(path: Path) -> dict | None:
    return json.loads(path.read_text()) if path.exists() else None


def save_cached(path: Path, record: dict) -> None:
    path.write_text(json.dumps(record))


async def cached_llm_call(client, model: str, messages: list[dict], cache_dir: str = "cache") -> str:
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    key = hashlib.md5(f"{model}{json.dumps(messages, sort_keys=True)}".encode()).hexdigest()
    path = Path(cache_dir) / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text())["response"]
    response = await client.messages.create(model=model, messages=messages, max_tokens=2048)
    result = response.content[0].text
    path.write_text(json.dumps({"response": result, "model": model}))
    return result
