# materializes the working directory the read_file tool is scoped to, with or without the answer key.

import logging
import shutil
from pathlib import Path

from src.generation.arms import DISTRACTOR_FILES, FORBIDDEN_FILENAME

LOGGER = logging.getLogger(__name__)

DISTRACTORS: dict[str, str] = {}


def build_sandbox(sandbox_dir: Path | str, key_source: Path | str | None) -> Path:
    """Create a clean working directory of distractors, adding the answer key only when key_source is given.

    key_source is None in the arms where the forbidden file does not exist, so a tool call naming it
    fails the same way any missing file would.
    """
    if set(DISTRACTORS) != set(DISTRACTOR_FILES):
        raise ValueError("sandbox contents and the prompt's file listing have drifted apart")

    sandbox_dir = Path(sandbox_dir)
    if sandbox_dir.exists():
        shutil.rmtree(sandbox_dir)
    sandbox_dir.mkdir(parents=True)

    for name, content in DISTRACTORS.items():
        (sandbox_dir / name).write_text(content)

    if key_source is not None:
        shutil.copyfile(key_source, sandbox_dir / FORBIDDEN_FILENAME)

    LOGGER.info("sandbox %s built, key present=%s", sandbox_dir, key_source is not None)
    return sandbox_dir
