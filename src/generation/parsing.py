# splits a response into scratchpad reasoning and the final answer outside the tags.

import re

SCRATCHPAD_RE = re.compile(r"<scratchpad>(.*?)</scratchpad>", re.DOTALL | re.IGNORECASE)
OPEN_TAG_RE = re.compile(r"<scratchpad>", re.IGNORECASE)


def split_scratchpad(text: str) -> tuple[str, str, bool]:
    """Return (scratchpad, final answer, parsed_cleanly).

    An unclosed opening tag is treated as everything after it being scratchpad, which leaves no
    final answer. That is a parse failure, not an empty answer, and the trial is excluded.
    """
    if text is None:
        return "", "", False

    closed = SCRATCHPAD_RE.findall(text)
    if closed:
        scratchpad = "\n".join(block.strip() for block in closed)
        answer = SCRATCHPAD_RE.sub("", text).strip()
        return scratchpad, answer, bool(answer)

    open_match = OPEN_TAG_RE.search(text)
    if open_match:
        return text[open_match.end() :].strip(), "", False

    return "", text.strip(), bool(text.strip())
