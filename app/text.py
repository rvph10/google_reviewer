import re
from difflib import SequenceMatcher

TRANSLATED = "(Translated by Google)"
ORIGINAL = "(Original)"


def original_text(comment: str) -> str:
    """Strip the translation Google appends to reviews written in another language."""
    if ORIGINAL in comment:
        return comment.split(ORIGINAL, 1)[1].strip()
    if TRANSLATED in comment:
        return comment.split(TRANSLATED, 1)[0].strip()
    return comment.strip()


def _normalize(text: str) -> str:
    return re.sub(r"\W+", " ", text.lower()).strip()


def too_similar(text: str, others: list[str], threshold: float = 0.8) -> bool:
    candidate = _normalize(text)
    return any(SequenceMatcher(None, candidate, _normalize(o)).ratio() >= threshold for o in others)
