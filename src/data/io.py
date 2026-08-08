import json
from pathlib import Path


def load_jsonl(path: Path | str, num_tasks: int | None = None) -> list[dict]:
    """Read a jsonl dataset, optionally truncated to the first num_tasks records.

    num_tasks=None reads everything. Blank lines are skipped so a trailing newline is harmless.
    """
    lines = Path(path).read_text().splitlines()
    records = [json.loads(line) for line in lines if line.strip()]
    return records[:num_tasks] if num_tasks else records


def _round_floats(value):
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, dict):
        return {k: _round_floats(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_round_floats(v) for v in value]
    return value


def write_jsonl(records: list[dict], path: Path | str) -> Path:
    """Write records one per line, rounding every float to 4 decimal places on the way out."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(_round_floats(r)) + "\n" for r in records))
    return path
