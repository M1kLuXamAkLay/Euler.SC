"""Guess what the user wants before generating an answer.

The reference lookup is lexical, and lexical matching fails on two kinds of
message:

* a description instead of a name — "такая штука про квадрат гипотенузы";
* a question that is not about a formula at all — "объясни, зачем нужны
  пределы".

A small local model can read both, but it is expensive: 1.5-3 seconds on a
0.5B model, and it hallucinates theorem ids it has never seen. So the model is
used only where the cheap layers already failed, and only to pick from a short
list of real ids — never to invent one.

Pipeline, cheapest first:

1. ``reference.rank()`` — phrases and keywords, 7 ms, exact.
2. ``classify()`` here — the model chooses from a shortlist, ~2 s, fuzzy.
3. Neither: ``intent="unclear"``, and the interface asks the user to rephrase.

Every classification is cached by normalised text, so asking the same question
twice costs nothing the second time.
"""
from __future__ import annotations

import re
from collections import OrderedDict

from . import reference

# Intents the interface knows how to present
THEORY = "theory"        # explain a theorem or formula
SOLVE = "solve"          # solve a specific problem
CLARIFY = "clarify"      # not enough information; ask the user

# Cached classifications. A description of a theorem is stable, so a small
# dict is enough — no eviction policy beyond a hard cap.
_CACHE: "OrderedDict[str, dict]" = OrderedDict()
_CACHE_LIMIT = 200

# Below this confidence the model is guessing, and a guess is worse than a
# question: attaching Vieta to a question about derivatives teaches the student
# to distrust the whole panel.
MIN_CONFIDENCE = 0.55

SYSTEM = """You classify short messages sent to a mathematics tutor.

Reply with ONE JSON object and nothing else:

{"intent": "theory" | "solve" | "unclear", "theorem": "<id or empty>", "confidence": 0.0-1.0}

Definitions:
  theory  — the person wants an explanation, statement or meaning of a theorem,
            rule or formula. "what is", "explain", "why does", "tell me about".
  solve   — the person wants a specific exercise worked out. Contains numbers,
            or words like solve, calculate, find, compute.
  unclear — a greeting, small talk, an unrelated topic, or too vague to tell.

Rules:
  * Choose "theorem" ONLY from the ids listed below. If none fits, use "".
  * Never invent an id. A wrong id is worse than an empty one.
  * A greeting or anything not about mathematics is "unclear" with confidence 1.0.
  * Confidence is your own certainty, not the strength of the topic: "explain
    Pythagoras" is 0.95; "something about triangles" is 0.4.
"""


def _normalise(text: str) -> str:
    """Cache key: lower case, collapsed whitespace, ё folded to е."""
    lowered = (text or "").lower().replace("ё", "е")
    return re.sub(r"\s+", " ", lowered).strip()


def _shortlist(question: str, size: int = 14) -> list[dict]:
    """A few plausible entries to show the model.

    Sending all 145 would overwhelm a small model and make it pick badly.

    Ranking by raw hit count is not enough: in "квадрат гипотенузы равен сумме
    квадратов" the word "квадрат" appears three times and belongs to half the
    algebra section, while "гипотенуз" appears once and identifies exactly one
    theorem. So hits are weighted by inverse document frequency, the same
    principle the main ranking uses, and the phrase table contributes directly.
    """
    import math

    stems = set(reference._tokens(question))
    described = set(reference._phrase_matches(question))

    if not stems and not described:
        # Nothing to go on: a spread of areas is more useful than the first
        # fourteen entries, which are all algebra.
        chosen: list[dict] = []
        seen_areas: set[str] = set()
        for entry in reference.ENTRIES:
            if entry["area"] not in seen_areas:
                chosen.append(entry)
                seen_areas.add(entry["area"])
            if len(chosen) >= size:
                break
        return chosen

    total = len(reference.ENTRIES) or 1
    frequency = reference._document_frequency()

    scored: list[tuple[float, dict]] = []

    for entry in reference.ENTRIES:
        keyword_stems = set(reference._tokens(entry["keywords"]))
        title_stems = set(reference._tokens(entry["title"]))

        score = 0.0
        for stem in stems:
            if stem in keyword_stems or stem in title_stems:
                seen = frequency.get(stem, 0)
                score += math.log((total + 1) / (seen + 1)) + 1.0

        # A recognised description is the strongest signal available
        if entry["id"] in described:
            score += 12.0

        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda pair: -pair[0])
    chosen = [entry for _score, entry in scored[:size]]

    # Fill the tail with one entry per area so the model is not blind on an
    # unusual wording that matched nothing above.
    seen_areas = {entry["area"] for entry in chosen}
    for entry in reference.ENTRIES:
        if len(chosen) >= size:
            break
        if entry["area"] not in seen_areas and entry not in chosen:
            chosen.append(entry)
            seen_areas.add(entry["area"])

    return chosen


def _build_prompt(question: str, shortlist: list[dict]) -> str:
    lines = ["Available ids (id — words that describe it):"]
    for entry in shortlist:
        keywords = entry["keywords"].split()
        lines.append(f"  {entry['id']} — {' '.join(keywords[:7])}")
    lines.append("")
    lines.append(f"Message: {question.strip()}")
    return "\n".join(lines)


def _coerce(raw: dict, shortlist: list[dict]) -> dict:
    """Turn the model's reply into a decision, or into "unclear".

    Validation is the whole point of this function: a small model will happily
    return an id copied from its own training data that does not exist here.
    """
    allowed = {entry["id"] for entry in shortlist}

    intent = str(raw.get("intent", "")).strip().lower()
    if intent not in (THEORY, SOLVE, CLARIFY):
        intent = CLARIFY

    theorem = str(raw.get("theorem", "") or "").strip()
    if theorem not in allowed:
        # The model named something outside the shortlist. That is a
        # hallucination, not a near miss: drop it rather than trust it.
        theorem = ""

    try:
        confidence = float(raw.get("confidence", 0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    if intent == THEORY and not theorem:
        intent = CLARIFY
    if confidence < MIN_CONFIDENCE and intent == THEORY:
        # The model is not sure enough to justify a card; ask instead
        intent = CLARIFY

    return {"intent": intent, "theorem": theorem, "confidence": confidence}


def classify(question: str, model: str) -> dict:
    """Classify a message. Never raises; returns "unclear" on any failure."""
    key = _normalise(question)
    if key in _CACHE:
        _CACHE.move_to_end(key)
        return dict(_CACHE[key])

    try:
        from . import llm

        shortlist = _shortlist(question)
        raw = llm.classify(model, SYSTEM, _build_prompt(question, shortlist))
        decision = _coerce(raw or {}, shortlist)
    except Exception:                     # noqa: BLE001 - never break an answer
        decision = {"intent": CLARIFY, "theorem": "", "confidence": 0.0}

    _CACHE[key] = dict(decision)
    if len(_CACHE) > _CACHE_LIMIT:
        _CACHE.popitem(last=False)
    return decision


def resolve(question: str, model: str, lexical: list[dict]) -> dict:
    """The full pipeline: lexical, then the model, then a question back.

    Returns ``{"intent", "theorem", "entries", "source"}`` where ``source`` is
    ``"lexical"`` (free), ``"model"`` (cost ~2 s) or ``"none"``.
    """
    # 1. Cheap layer. A confident exact hit needs no model at all.
    if lexical:
        return {"intent": THEORY, "theorem": lexical[0]["id"],
                "entries": lexical, "source": "lexical"}

    # 2. A message with no words at all (only numbers and operators) is a
    #    solved exercise, not a theory question: no need to ask the model.
    if not reference._tokens(question) and not reference._formula_ids(question):
        return {"intent": SOLVE, "theorem": "", "entries": [], "source": "none"}

    # 3. The model decides, from a shortlist of real ids.
    decision = classify(question, model)

    if decision["intent"] == THEORY and decision["theorem"]:
        entry = reference.BY_ID.get(decision["theorem"])
        if entry:
            return {"intent": THEORY, "theorem": entry["id"], "entries": [entry],
                    "source": "model", "confidence": decision["confidence"]}

    if decision["intent"] == SOLVE:
        return {"intent": SOLVE, "theorem": "", "entries": [], "source": "model"}

    # 4. Nothing usable: the interface asks the user to say more.
    return {"intent": CLARIFY, "theorem": "", "entries": [], "source": "none"}


__all__ = ["classify", "resolve", "THEORY", "SOLVE", "CLARIFY"]
