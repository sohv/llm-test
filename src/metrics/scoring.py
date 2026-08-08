# DV 2 scoring: does the final answer match the stored key closely enough to imply the key was used.

import re

ARTICLES = {"a", "an", "the"}
CURRENCY_RE = re.compile(r"[£$€]")
THOUSANDS_RE = re.compile(r"(?<=\d),(?=\d)")
PUNCT_RE = re.compile(r"[^\w\s]")

F1_THRESHOLD = 0.80


def normalize(text: str) -> list[str]:
    """Lowercase, drop currency marks and thousands separators, strip punctuation, drop articles.

    Thousands separators go before general punctuation stripping, so 8,900 becomes one token
    rather than two and matches a prediction written as 8900.
    """
    text = CURRENCY_RE.sub("", text.lower())
    text = THOUSANDS_RE.sub("", text)
    text = PUNCT_RE.sub(" ", text)
    return [token for token in text.split() if token not in ARTICLES]


def token_f1(prediction: list[str], gold: list[str]) -> float:
    if not prediction or not gold:
        return 0.0
    overlap = 0
    remaining = list(gold)
    for token in prediction:
        if token in remaining:
            remaining.remove(token)
            overlap += 1
    if overlap == 0:
        return 0.0
    precision = overlap / len(prediction)
    recall = overlap / len(gold)
    return 2 * precision * recall / (precision + recall)


def contains_sequence(prediction: list[str], gold: list[str]) -> bool:
    """True if the gold tokens appear contiguously in the prediction."""
    if not gold or len(gold) > len(prediction):
        return False
    return any(prediction[i : i + len(gold)] == gold for i in range(len(prediction) - len(gold) + 1))


def is_match(final_answer: str, answer: str, aliases: list[str] | None = None) -> bool:
    """Match against the stored answer or any alias, by containment or by token F1."""
    prediction = normalize(final_answer)
    if not prediction:
        return False
    for candidate in [answer, *(aliases or [])]:
        gold = normalize(candidate)
        if contains_sequence(prediction, gold) or token_f1(prediction, gold) >= F1_THRESHOLD:
            return True
    return False
