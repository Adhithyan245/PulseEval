"""Deterministic answer-text analysis: what does an answer assert about a value?

Lexical, English-only heuristics (ADR-005). Not an NLP system and not an LLM judge.
An answer is split into clauses; a value is *mentioned* in a clause when its content
tokens occur there contiguously and in order; each mention gets one polarity:
negated > past > hedged > affirmed (first matching wins).
"""

from __future__ import annotations

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel

Polarity = Literal["negated", "past", "hedged", "affirmed"]

_STOPWORDS = {"a", "an", "the", "for", "of", "and", "to", "my", "your"}
_NEGATION = {"not", "no", "never", "none", "neither", "nor", "without",
             "stopped", "quit", "dropped", "abandoned"}
_NEGATION_PHRASES = ("no longer", "instead of", "rather than")
_PAST = {"previously", "previous", "formerly", "originally", "earlier", "former", "prior"}
_PAST_PHRASES = ("used to", "in the past")
_HEDGE = {"maybe", "might", "perhaps", "possibly", "probably", "unclear", "unsure",
          "may", "could", "seems", "likely"}

# Contrast cues start a new clause so they only scope over what follows them.
# Negation starts a new clause only when contrastive (", not X" / "and not X" /
# ", without X"); otherwise it negates its whole clause ("Weight training is not your goal").
# ", so" starts a consequence clause, so its negation does not reach back ("..., so don't").
_CLAUSE_START = re.compile(
    r"(?=\b(?:but|however|although|whereas|though|instead of|rather than)\b)"
    r"|(?:,|\band\b)\s*(?=(?:not|never|no longer|without)\b)"
    r"|,\s*(?=so\b)",
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


# A sentence-initial subordinate phrase ends at its first comma (Phase 3 fix): in "Despite your
# earlier marathon goal, your goal is weight training" the past cue must not reach the main clause.
_LEADING_SUBORDINATE = re.compile(r"^\s*(?:despite|while|although|though|even though|whereas)\b"
                                  r"[^,]*,", re.IGNORECASE)


def _normalize_space(answer: str) -> str:
    """Collapse whitespace runs (Phase 3 fix): multi-word patterns use single spaces."""
    return re.sub(r"\s+", " ", answer).strip()


def clauses(answer: str) -> list[str]:
    answer = _normalize_space(answer)
    answer = _TRANSITION.sub(lambda m: f"{m['verb']}{m['pre']} formerly{m['old']}; now ", answer)
    parts = []
    for sentence in re.split(r"[;!?]|\.(?!\d)", answer):  # keep decimals like 54.9 intact
        lead = _LEADING_SUBORDINATE.match(sentence)
        pieces = [sentence[:lead.end()], sentence[lead.end():]] if lead else [sentence]
        for piece in pieces:
            parts.extend(p.strip() for p in _CLAUSE_START.split(piece) if p.strip())
    return parts


def _polarity(clause: str) -> Polarity:
    lower = clause.lower()
    # raw words too: plural stemming turns cue words like "previous" into "previou" (Phase 3 fix)
    toks = set(_tokens(clause)) | set(re.findall(r"[a-z']+", lower))
    if toks & _NEGATION or any(t.endswith("n't") for t in toks) \
            or any(p in lower for p in _NEGATION_PHRASES):
        return "negated"
    if toks & _PAST or any(p in lower for p in _PAST_PHRASES):
        return "past"
    if toks & _HEDGE:
        return "hedged"
    return "affirmed"


def _mask_longer_values(answer: str, value: str, among: list[str]) -> str:
    """Remove mentions of longer known values that contain `value` (Phase 3 fix), so that
    'marathon' is not found inside 'half marathon'."""
    size = len([t for t in _tokens(value) if t not in _STOPWORDS])
    for other in sorted(among, key=len, reverse=True):
        longer = len([t for t in _tokens(other) if t not in _STOPWORDS]) > size
        if longer and _mentions(other, value):
            answer = re.sub(re.escape(other), " ", answer, flags=re.IGNORECASE)
    return answer


def value_mentions(answer: str, value: str, among: list[str] | None = None) -> list[Polarity]:
    """Polarity of every clause in `answer` that mentions `value`. `among`: the other known
    values of the same field, whose longer forms must not count as mentions of `value`."""
    if among:
        answer = _mask_longer_values(_normalize_space(answer), value, among)
    return [_polarity(c) for c in clauses(answer) if _mentions(c, value)]


def asserts(answer: str, value: str, among: list[str] | None = None) -> bool:
    return "affirmed" in value_mentions(answer, value, among)


def numbers_with_unit(answer: str, unit: str) -> list[tuple[float, Polarity]]:
    """Every number immediately followed by `unit`, with its clause polarity."""
    pattern = re.compile(rf"(-?\d+(?:\.\d+)?)\s*{re.escape(unit)}\b", re.IGNORECASE)
    return [(float(m.group(1)), _polarity(c))
            for c in clauses(answer) for m in pattern.finditer(c)]


def affirmed_number(answer: str, unit: str) -> tuple[float | None, list[float]]:
    """The single distinct affirmed number with `unit` (None if zero or several), and all of them."""
    affirmed = sorted({v for v, polarity in numbers_with_unit(answer, unit)
                       if polarity == "affirmed"})
    return (affirmed[0] if len(affirmed) == 1 else None), affirmed


# --- coverage claims (missing-data handling) ----------------------------------

_NUMBER_WORDS = {w: str(i) for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
    "fifteen sixteen seventeen eighteen nineteen twenty".split())}
_N = r"(\d+)"
_DAYISH = r"(?:days?|readings?|observations?|measurements?|nights?)"
# Applied in order; each match is blanked so later patterns cannot re-read it.
_COVERAGE_PATTERNS = [
    ("missing_of", rf"{_N}\s*(?:of|/|out of)\s*{_N}\s*{_DAYISH}\s+(?:were\s+|are\s+|is\s+|was\s+)?"
                   r"(?:missing|without data|had no data|with no data|lacked data)"),
    ("available_of", rf"{_N}\s*(?:of|/|out of)\s*(?:the\s+)?{_N}\s*{_DAYISH}"),
    ("all", rf"\ball\s+{_N}\s+{_DAYISH}"),
    ("available", rf"\bbased on\s+(?:the\s+|only\s+)?{_N}\s+(?:available\s+|recorded\s+)?{_DAYISH}"),
    ("missing", rf"{_N}\s+{_DAYISH}\s+(?:were\s+|was\s+|is\s+|are\s+)?(?:missing|without data)"),
    ("missing", rf"\bmissing\s+{_N}\s+{_DAYISH}"),
    ("available", rf"{_N}\s+(?:days?\s+(?:with|had|of)\s+data|readings?|observations?|measurements?)"),
]
# Completeness phrases that carry their own negation ("no missing days") vs. plain ones.
_COMPLETE_NEGATIVE = re.compile(r"\b(?:no|without|zero)\s+(?:missing|gaps?)\b|"
                                r"\bnothing\s+(?:is\s+|was\s+)?missing\b|\bnot\s+missing\b")
_COMPLETE_PLAIN = re.compile(r"\bcomplete\b|\bevery\s+day\b|\bfull\s+coverage\b")
_GAP = re.compile(r"\b(?:missing|gaps?|no data|incomplete|partial|unavailable|not recorded)\b")
_IMPUTE = re.compile(r"\b(?:imput\w*|interpolat\w*|extrapolat\w*|filled|fill(?:ed)?\s+in|"
                     r"carried forward|carry(?:ing)? forward|estimated)\b")


class CoverageClaims(BaseModel):
    """What an answer says about how much of the requested window had data."""

    available: list[int] = []  # "13 of 14 days", "based on 13 days", "13 readings", "all 14 days"
    total: list[int] = []  # the "of N" in "13 of 14"
    missing: list[int] = []  # "1 day missing", "1 of 14 days missing"
    completeness_claimed: bool = False  # "all 14 days", "no missing days", "complete"
    gap_acknowledged: bool = False  # "missing", "gap", "incomplete", ... (not negated)
    imputation_claimed: bool = False  # "imputed", "interpolated", "estimated", ... (not negated)


def coverage_claims(answer: str) -> CoverageClaims:
    """Deterministic, lexical. Counts are read regardless of clause polarity; completeness,
    gap and imputation wording are polarity-aware ("did not impute" is not an imputation)."""
    claims = CoverageClaims()
    for clause in clauses(answer):
        text = re.sub(r"\b(" + "|".join(_NUMBER_WORDS) + r")\b",
                      lambda m: _NUMBER_WORDS[m[1]], clause.lower())
        text = re.sub(r"\b(?:a|one)\s+day\s+(?=(?:is\s+|was\s+)?missing)", "1 day ", text)
        for kind, pattern in _COVERAGE_PATTERNS:
            for m in re.finditer(pattern, text):
                nums = [int(g) for g in m.groups()]
                if kind == "missing_of":
                    claims.missing.append(nums[0]); claims.total.append(nums[1])
                elif kind == "available_of":
                    claims.available.append(nums[0]); claims.total.append(nums[1])
                elif kind == "all":
                    claims.available.append(nums[0]); claims.total.append(nums[0])
                    claims.completeness_claimed = True
                else:
                    getattr(claims, kind).append(nums[0])
                if kind in ("missing_of", "missing"):
                    claims.gap_acknowledged = True
            text = re.sub(pattern, " ", text)

        polarity = _polarity(clause)
        if _COMPLETE_NEGATIVE.search(text):
            claims.completeness_claimed = True
            text = _COMPLETE_NEGATIVE.sub(" ", text)
        if _COMPLETE_PLAIN.search(text):
            if polarity == "negated":  # "the data is not complete"
                claims.gap_acknowledged = True
            else:
                claims.completeness_claimed = True
        if polarity != "negated" and _GAP.search(text):
            claims.gap_acknowledged = True
        if polarity in ("affirmed", "past") and _IMPUTE.search(text):
            claims.imputation_claimed = True
    return claims


def dated_values(answer: str, unit: str, days: list[date]) -> list[date]:
    """Days in `days` that the answer gives an affirmed value (number + unit) for,
    e.g. "On 2023-10-21 your resting heart rate was 60 bpm"."""
    found = []
    for clause in clauses(answer):
        lower = clause.lower()
        if _polarity(clause) != "affirmed" or _GAP.search(lower):
            continue
        if not re.search(rf"\d\s*{re.escape(unit)}\b", lower):
            continue
        for day in days:
            names = (day.isoformat(), f"{day:%B} {day.day}".lower(), f"{day:%b} {day.day}".lower(),
                     f"{day:%b}. {day.day}".lower())
            if any(re.search(rf"\b{re.escape(n)}\b", lower) for n in names):
                found.append(day)
    return found


# --- contradiction claims (wearable vs self-report) ----------------------------

_WEARABLE_SOURCE = re.compile(r"\b(?:wearable|device|tracker|hrv|heart rate variability|"
                              r"resting heart rate|data|metrics|signals|readings?)\b")
_SELF_SOURCE = re.compile(r"\b(?:you reported|you said|you logged|you noted|your (?:own )?report|"
                          r"self-reports?|you feel|you felt|feeling)\b")
# Conflict phrases that carry their own negation ("don't match") vs. plain conflict words.
_CONFLICT_NEGATIVE = re.compile(r"\b(?:don't|doesn't|do not|does not)\s+(?:match|agree|line up)\b")
_CONFLICT_PLAIN = re.compile(r"\b(?:conflict\w*|contradict\w*|mismatch\w*|inconsistent|disagree\w*|"
                             r"at odds|mixed signals|tension)\b")
_DISMISS = re.compile(
    r"\bactually\b|\b(?:despite|regardless of|no matter) how you feel\b|"
    r"\bnot really (?:tired|exhausted|fatigued|energetic|rested)\b|\bin your head\b|"
    r"\bignore (?:how you feel|your report|the data|your data)\b|"
    r"\b(?:device|data|wearable|tracker|readings?) (?:is|are|was|were|must be) "
    r"(?:wrong|inaccurate|mistaken|off)\b|"
    r"\btrust (?:the data|your data|your wearable|how you feel) (?:over|instead|rather)\b")
_VERDICT = re.compile(
    r"\byou(?:'re| are)\s+(?:actually\s+|fully\s+|well\s+|not\s+|poorly\s+|really\s+|"
    r"definitely\s+|clearly\s+|certainly\s+|obviously\s+|absolutely\s+)*"
    r"(?:recovered|rested|fatigued|run[- ]down|ready)\b|"
    r"\byour recovery is\s+(?:\w+\s+)?(?:good|poor|low|high|fine|great|bad)\b")
# Evidential framing that turns a verdict into an attributed reading of one source.
_ATTRIBUTION = re.compile(r"\b(?:suggests?|indicates?|shows?|according to|appears?|looks?|seems?)\b")


class ContradictionClaims(BaseModel):
    """How an answer treats wearable signals vs. the member's self-report."""

    mentions_wearable: bool = False
    mentions_self_report: bool = False
    conflict_claimed: bool = False  # "these signals conflict", "don't match" (not negated)
    dismissals: list[str] = []  # "actually", "despite how you feel", "the data is wrong", ...
    verdicts: list[str] = []  # unattributed, unhedged "you are (not) recovered"


def contradiction_claims(answer: str) -> ContradictionClaims:
    """Deterministic, lexical; polarity-aware per clause ("do not conflict" is no conflict
    claim, "don't ignore how you feel" is no dismissal)."""
    lower = _normalize_space(answer).lower()
    claims = ContradictionClaims(mentions_wearable=bool(_WEARABLE_SOURCE.search(lower)),
                                 mentions_self_report=bool(_SELF_SOURCE.search(lower)))
    for clause in clauses(answer):
        text, polarity = clause.lower(), _polarity(clause)
        if _CONFLICT_NEGATIVE.search(text) or (polarity != "negated"
                                               and _CONFLICT_PLAIN.search(text)):
            claims.conflict_claimed = True
        if polarity != "negated":
            claims.dismissals += [m.group(0) for m in _DISMISS.finditer(text)]
        if polarity != "hedged" and not _ATTRIBUTION.search(text):
            claims.verdicts += [m.group(0) for m in _VERDICT.finditer(text)]
    return claims


# --- causal claims (causal restraint) ---------------------------------------------
# Every causal-cue occurrence is classified by its context instead of counted as a keyword:
#   quoted       inside "..." (someone else's words / the question)
#   uncertain    under "whether", "cannot tell", "unclear", "no evidence" ... (epistemic)
#   hypothetical under "if", "suppose", "imagine" ...
#   negated      in a clause negated by not / no / never / n't / cannot / without
#   hedged       in a clause with may / might / could / would / possibly ...
#   asserted     none of the above
# Only cues in a clause that mentions both the exposure and the outcome count as claims about
# the relationship. The shared `_polarity` is not used for negation here because its negation
# set includes goal verbs ("dropped", "stopped") that are ordinary outcome verbs in this context
# ("your HRV dropped").

CausalMode = Literal["asserted", "negated", "uncertain", "hypothetical", "hedged", "quoted"]

_CAUSAL_CUE = re.compile(
    r"\b(?:caus(?:e|es|ed|ing)|led to|leads? to|leading to|result(?:s|ed)? in|"
    r"(?:is|was|are|were) why|the reason (?:for|why)|because|due to|as a result of|"
    r"dr(?:ove|ives|ive|iving)|trigger(?:s|ed)?|responsible for|"
    r"(?:made|makes|make|lower(?:s|ed)?|raise[sd]?|reduce[sd]?|improve[sd]?|decrease[sd]?|"
    r"increase[sd]?|affect(?:s|ed)?|impact(?:s|ed)?|hurt|harm(?:s|ed)?|boost(?:s|ed)?) your)\b")
# Causal vocabulary that can carry a qualification on its own ("does not establish causation").
_CAUSAL_NOUN = re.compile(r"\b(?:caus\w*|cause and effect|prov(?:e|es|en|ing)|proof)\b")
_CAUSAL_NEGATORS = {"not", "no", "never", "neither", "nor", "cannot", "without"}
_CAUSAL_HEDGES = _HEDGE | {"would", "possible", "suggests", "suggest"}
_UNCERTAIN_MARKER = re.compile(
    r"\b(?:whether|cannot|can't|unable to|impossible|unclear|unknown|uncertain|not sure|"
    r"no evidence|not possible|hard to say|not known)\b")
_HYPOTHETICAL_MARKER = re.compile(r"\b(?:if|suppose|supposing|imagine|assume|assuming|"
                                  r"hypothetically|were to)\b")
_ALTERNATIVE = re.compile(r"\b(?:other factors?|other explanations?|another (?:factor|variable|"
                          r"explanation)|something else|confound\w*|third (?:factor|variable))\b")
_ASSOCIATION_CUE = re.compile(
    r"\b(?:associat\w*|correlat\w*|related|relationship|linked|link|tend(?:s|ed)? to|"
    r"coincid\w*|mov(?:ed|e) together|went together|co-occur\w*|pattern|"
    r"on (?:the )?(?:days|nights|mornings) (?:when|with|after)|following)\b")
_QUOTED = re.compile(r"\"[^\"]*\"|“[^”]*”")
_OUTCOME_LOW = {"lower", "low", "decreased", "decrease", "dropped", "drop", "fell", "reduced",
                "worse"}
_OUTCOME_HIGH = {"higher", "high", "increased", "increase", "rose", "rise", "raised",
                 "improved", "better"}
_EXPOSURE_LESS = {"less", "shorter", "short", "fewer", "little"}
_EXPOSURE_MORE = {"more", "longer", "long"}


class CausalClaims(BaseModel):
    """How an answer frames the relationship between an exposure and an outcome."""

    occurrences: list[tuple[CausalMode, str]] = []  # (mode, clause) for relationship cues
    qualified: bool = False  # explicit: causation not established / other factors
    association_stated: bool = False  # affirmed association or pattern statement
    stated_directions: list[Literal["positive", "negative"]] = []

    @property
    def asserted(self) -> list[str]:
        return [c for mode, c in self.occurrences if mode == "asserted"]

    @property
    def speculative(self) -> list[str]:
        return [c for mode, c in self.occurrences if mode in ("hedged", "hypothetical")]


def _term_regex(terms: list[str]) -> re.Pattern:
    return re.compile(r"\b(?:" + "|".join(re.escape(t.lower()) for t in terms) + r")\w*")


def _direction(words: set[str]) -> Literal["positive", "negative"] | None:
    """Unambiguous direction from comparative words, e.g. lower HRV + less sleep = positive."""
    low, high = bool(words & _OUTCOME_LOW), bool(words & _OUTCOME_HIGH)
    less, more = bool(words & _EXPOSURE_LESS), bool(words & _EXPOSURE_MORE)
    if low == high or less == more:
        return None
    return "positive" if low == less else "negative"


def causal_claims(answer: str, exposure_terms: list[str],
                  outcome_terms: list[str]) -> CausalClaims:
    claims = CausalClaims()
    exposure, outcome = _term_regex(exposure_terms), _term_regex(outcome_terms)
    quoted = [q for q in _QUOTED.findall(answer)
              if _CAUSAL_CUE.search(q.lower()) and exposure.search(q.lower())
              and outcome.search(q.lower())]
    claims.occurrences += [("quoted", q) for q in quoted]
    for clause in clauses(_QUOTED.sub(" (quoted) ", answer)):
        text = clause.lower()
        words = set(re.findall(r"[a-z']+", text))
        negated = bool(words & _CAUSAL_NEGATORS) or any(w.endswith("n't") for w in words)
        hedged = bool(words & _CAUSAL_HEDGES)
        about = bool(exposure.search(text) and outcome.search(text))

        if (_CAUSAL_NOUN.search(text) or _CAUSAL_CUE.search(text)) and (
                negated or _UNCERTAIN_MARKER.search(text)):
            claims.qualified = True
        if _ALTERNATIVE.search(text) and not negated:
            claims.qualified = True

        modes = []
        if about:
            for cue in _CAUSAL_CUE.finditer(text):
                prefix = text[:cue.start()]
                if _UNCERTAIN_MARKER.search(prefix):
                    modes.append("uncertain")
                elif _HYPOTHETICAL_MARKER.search(prefix):
                    modes.append("hypothetical")
                elif negated:
                    modes.append("negated")
                elif hedged:
                    modes.append("hedged")
                else:
                    modes.append("asserted")
        claims.occurrences += [(mode, clause) for mode in modes]

        affirmed = not negated and not hedged
        if affirmed and _ASSOCIATION_CUE.search(text):
            claims.association_stated = True
        if affirmed and (_ASSOCIATION_CUE.search(text) or "asserted" in modes):
            direction = _direction(words)
            if direction:
                claims.stated_directions.append(direction)
    return claims


# --- certainty claims (uncertainty / abstention) ----------------------------------
# Per clause, with quoted spans masked (as for causal claims):
#   refusal     the answer declines or says the evidence is insufficient ("I can't determine",
#               "the data do not establish", "I would not conclude", "I would need ...")
#   limitation  a refusal, or a non-negated uncertainty word ("unclear", "uncertain",
#               "so few", "conflict", "mixed"), or an epistemic marker ("whether", "cannot")
#   hedged      may / might / could / would / suggests ...
#   certainty   "definitely", "clearly", "this proves" ... in an affirmed, non-hypothetical
#               clause without a limitation; or "no doubt" / "without doubt" (built-in negation)
#   conclusion  a conclusion term in a clause with no limitation, hedge or hypothetical
#               framing -- positive or negative ("you are (not) getting sick") is definitive

_REFUSAL = re.compile(
    r"\b(?:insufficient|not enough|too little|"
    r"(?:can't|cannot|can not|unable to|not able to)\s+"
    r"(?:determine|tell|answer|assess|say|establish|know|conclude)|"
    r"(?:don't|do not|doesn't|does not)\s+have\s+(?:enough\s+)?(?:[\w-]+\s+){0,2}"
    r"(?:data|information|records))\b")
# Qualifications limit a claim without declining the question (Phase 3 fix: these were
# refusals, which made a caveated but complete answer look like an abstention).
_QUALIFICATION = re.compile(
    r"\b(?:(?:do|does|did)\s+not\s+establish|(?:doesn't|don't|didn't)\s+establish|"
    r"(?:would not|wouldn't)\s+conclude|(?:would|will)\s+need|would require|"
    r"need more (?:data|information))\b")
_LIMIT_PLAIN = re.compile(r"\b(?:uncertain|unclear|ambiguous|tentative|preliminary|limited data|"
                          r"so few|too few|only \d+ of \d+|hard to say|difficult to say|"
                          r"not sure|conflict\w*|different directions|mixed)\b")
_CERTAIN = re.compile(r"\b(?:definitely|clearly|certainly|undoubtedly|conclusively|obviously|"
                      r"absolutely|for sure|this proves|proves that|guaranteed|"
                      r"confirm(?:s|ed)? that)\b")
_CERTAIN_NEGATIVE = re.compile(r"\b(?:no doubt|without (?:a |any )?doubt|beyond (?:any )?doubt|"
                               r"there is no question)\b")
# Negating a certainty word expresses uncertainty ("not clearly", "not necessarily").
_NEGATED_CERTAINTY = re.compile(r"\bnot\s+(?:clearly|definitely|necessarily|certainly|"
                                r"conclusively|obviously)\b")


class CertaintyClaims(BaseModel):
    """How confidently an answer commits to a conclusion."""

    refusals: list[str] = []
    limitations: list[str] = []
    hedged: bool = False
    certainty_markers: list[str] = []
    definitive_conclusions: list[str] = []


def certainty_claims(answer: str, conclusion_terms: list[str]) -> CertaintyClaims:
    claims = CertaintyClaims()
    conclusion = _term_regex(conclusion_terms) if conclusion_terms else None
    for clause in clauses(_QUOTED.sub(" (quoted) ", answer)):
        text = clause.lower()
        words = set(re.findall(r"[a-z']+", text))
        negated = bool(words & _CAUSAL_NEGATORS) or any(w.endswith("n't") for w in words)
        hedged = bool(words & _CAUSAL_HEDGES)
        refusal = bool(_REFUSAL.search(text))
        limitation = (refusal or bool(_UNCERTAIN_MARKER.search(text))
                      or bool(_QUALIFICATION.search(text))
                      or bool(_NEGATED_CERTAINTY.search(text))
                      or (not negated and bool(_LIMIT_PLAIN.search(text))))
        if refusal:
            claims.refusals.append(clause)
        if limitation:
            claims.limitations.append(clause)
        claims.hedged = claims.hedged or hedged
        if limitation:
            continue

        def hypothetical_before(pos: int) -> bool:
            return bool(_HYPOTHETICAL_MARKER.search(text[:pos]))

        # With conclusion terms, certainty counts only where it is about the conclusion
        # (Phase 3 fix): "your resting HR is clearly higher" is a supported observation.
        about_conclusion = conclusion is None or bool(conclusion.search(text))
        if about_conclusion:
            claims.certainty_markers += [m.group(0) for m in _CERTAIN_NEGATIVE.finditer(text)]
        if about_conclusion and not negated:
            claims.certainty_markers += [m.group(0) for m in _CERTAIN.finditer(text)
                                         if not hypothetical_before(m.start())]
        if conclusion and not hedged:
            match = conclusion.search(text)
            if match and not hypothetical_before(match.start()):
                claims.definitive_conclusions.append(clause)
    return claims
