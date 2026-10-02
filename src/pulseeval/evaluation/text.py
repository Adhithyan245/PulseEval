"""Deterministic answer-text analysis: what does an answer assert about a value?

Lexical, English-only heuristics (ADR-005). Not an NLP system and not an LLM judge.
An answer is split into clauses; a value is *mentioned* in a clause when its content
tokens occur there contiguously and in order; each mention gets one polarity:
negated > past > hedged > affirmed (first matching wins).
"""

from __future__ import annotations

import re
from typing import Literal

Polarity = Literal["negated", "past", "hedged", "affirmed"]

_STOPWORDS = {"a", "an", "the", "for", "of", "and", "to", "my", "your"}
_NEGATION = {"not", "no", "never", "none", "neither", "nor", "without",
             "stopped", "quit", "dropped", "abandoned"}
_NEGATION_PHRASES = ("no longer", "instead of", "rather than")
_PAST = {"previously", "formerly", "originally", "earlier", "former", "prior"}
_PAST_PHRASES = ("used to", "in the past")
_HEDGE = {"maybe", "might", "perhaps", "possibly", "probably", "unclear", "unsure",
          "may", "could", "seems", "likely"}

# Contrast cues start a new clause so they only scope over what follows them.
# Negation starts a new clause only when contrastive (", not X" / "and not X");
# otherwise it negates its whole clause ("Weight training is not your goal").
_CLAUSE_START = re.compile(
    r"(?=\b(?:but|however|although|whereas|though|instead of|rather than)\b)"
    r"|(?:,|\band\b)\s*(?=(?:not|never|no longer)\b)",
    re.IGNORECASE,
)
# "switched from X to Y" -> X is past, Y is current.
_TRANSITION = re.compile(
    r"\b(?P<verb>switched|changed|moved|shifted|transitioned|went|updated)\b(?P<pre>[^.;]*?)"
    r"\bfrom\b(?P<old>[^.;]*?)\bto\b",
    re.IGNORECASE,
)


def _tokens(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9']+", text.lower())
    return [w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w
            for w in words]


def _mentions(clause: str, value: str) -> bool:
    """True when the value's content tokens occur contiguously, in order, in the clause."""
    wanted = [t for t in _tokens(value) if t not in _STOPWORDS]
    have = [t for t in _tokens(clause) if t not in _STOPWORDS]
    n = len(wanted)
    return n > 0 and any(have[i:i + n] == wanted for i in range(len(have) - n + 1))


def clauses(answer: str) -> list[str]:
    answer = _TRANSITION.sub(lambda m: f"{m['verb']}{m['pre']} formerly{m['old']}; now ", answer)
    parts = []
    for sentence in re.split(r"[;!?]|\.(?!\d)", answer):  # keep decimals like 54.9 intact
        parts.extend(p.strip() for p in _CLAUSE_START.split(sentence) if p.strip())
    return parts


def _polarity(clause: str) -> Polarity:
    lower = clause.lower()
    toks = set(_tokens(clause))
    if toks & _NEGATION or any(t.endswith("n't") for t in toks) \
            or any(p in lower for p in _NEGATION_PHRASES):
        return "negated"
    if toks & _PAST or any(p in lower for p in _PAST_PHRASES):
        return "past"
    if toks & _HEDGE:
        return "hedged"
    return "affirmed"


def value_mentions(answer: str, value: str) -> list[Polarity]:
    """Polarity of every clause in `answer` that mentions `value`."""
    return [_polarity(c) for c in clauses(answer) if _mentions(c, value)]


def asserts(answer: str, value: str) -> bool:
    return "affirmed" in value_mentions(answer, value)


def numbers_with_unit(answer: str, unit: str) -> list[tuple[float, Polarity]]:
    """Every number immediately followed by `unit`, with its clause polarity."""
    pattern = re.compile(rf"(-?\d+(?:\.\d+)?)\s*{re.escape(unit)}\b", re.IGNORECASE)
    return [(float(m.group(1)), _polarity(c))
            for c in clauses(answer) for m in pattern.finditer(c)]
