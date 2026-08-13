"""Weak supervision: assign classifier labels from seed terms.

This module is *the seam*. It exists so that the training pipeline has a
pluggable source of labels. Replacing it with LLM-produced labels (approach A
in the spec) changes nothing else in the pipeline.

Deliberately free of any Django import -- `scripts/train_classifier.py`
imports this on a machine with no Django settings configured.
"""

import re
from functools import lru_cache

from api.text_classifier.taxonomy import TAXONOMY

SEED_LABEL_THRESHOLD = 2
SEED_LABEL_MAX_CHARS = 4000

_STRONG_SCORE = 2
_WEAK_SCORE = 1


def _compile(terms: frozenset[str]) -> re.Pattern[str] | None:
    if not terms:
        return None
    # Longest first. This matters when one term is a prefix of another and
    # both end on a word boundary from the current position, e.g. "game" and
    # "game console" against "game console and game": alternation tries
    # branches left-to-right at each position, so with shortest-first
    # ("game" before "game console"), "game" wins the match at the position
    # where "game console" also starts, and re.findall only ever sees "game"
    # -- one distinct term for both occurrences, instead of "game" once and
    # "game console" once. Longest-first makes the more specific term win
    # where both could match, which is what distinct-match counting assumes.
    # (`\b...\b` alone does not solve this: it decides whether a *given*
    # branch matches at a position, not which branch is tried first.)
    # Tie-break alphabetically, not just by length: `sorted(terms, key=len,
    # reverse=True)` leaves equal-length terms in frozenset iteration order,
    # which (like the training-script bug this mirrors) varies by Python's
    # per-process string-hash randomization -- so the compiled pattern
    # *string* differs run-to-run even though it is behaviorally harmless
    # (two distinct equal-length alternatives can never match the same
    # span, so which one is tried first cannot change what matches). Stable
    # regardless of hash seed.
    alternation = "|".join(
        re.escape(t) for t in sorted(terms, key=lambda t: (-len(t), t))
    )
    return re.compile(rf"\b(?:{alternation})\b", re.IGNORECASE)


@lru_cache(maxsize=1)
def _patterns() -> dict[str, tuple[re.Pattern[str] | None, ...]]:
    return {
        name: (
            _compile(terms.strong),
            _compile(terms.weak),
            _compile(terms.exclude),
        )
        for name, terms in TAXONOMY.items()
    }


def reset_pattern_cache() -> None:
    """Clear the memoised compiled patterns.

    Not needed in production -- `TAXONOMY` is never mutated at runtime, so
    the cache is populated once and stays valid for the life of the process.
    This exists for tests that monkeypatch `TAXONOMY` to exercise different
    terms: without calling this afterwards, `score_text`/`label_text` would
    silently keep using the patterns compiled from the *previous* `TAXONOMY`,
    passing (or failing) for the wrong reason.
    """
    _patterns.cache_clear()


def _distinct_match_count(pattern: re.Pattern[str] | None, text: str) -> int:
    if pattern is None:
        return 0
    return len({m.lower() for m in pattern.findall(text)})


def score_text(text: str) -> dict[str, int]:
    """Per-label seed score. Excluded labels score 0."""
    text = text[:SEED_LABEL_MAX_CHARS]

    scores: dict[str, int] = {}
    for name, (strong, weak, exclude) in _patterns().items():
        if exclude is not None and exclude.search(text):
            scores[name] = 0
            continue

        scores[name] = _STRONG_SCORE * _distinct_match_count(
            strong, text
        ) + _WEAK_SCORE * _distinct_match_count(weak, text)

    return scores


def label_text(text: str) -> frozenset[str]:
    """Label names whose seed score meets the threshold."""
    return frozenset(
        name
        for name, score in score_text(text).items()
        if score >= SEED_LABEL_THRESHOLD
    )
