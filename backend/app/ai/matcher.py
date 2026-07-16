"""Field-matching: decide whether a discovered post is a genuine lead for THIS
client's trade.

This is the headline requirement — a plumber's bot must reply to plumbing leads,
not cleaning leads. We classify every discovered post against the client's trade
and service categories, returning a relevance score and a short reason.

Uses Claude when available; otherwise falls back to keyword-overlap scoring so
the pipeline still works offline.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..config import settings
from .client import get_ai

RELEVANCE_THRESHOLD = 0.5

_MATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "is_relevant": {"type": "boolean"},
        "score": {"type": "number"},
        "reason": {"type": "string"},
    },
    "required": ["is_relevant", "score", "reason"],
    "additionalProperties": False,
}

_SYSTEM = (
    "You are a lead-qualification engine for a local service business. "
    "You are given a community post and the service business's trade and "
    "service categories. Decide whether the post is someone who needs THIS "
    "business's services. Only mark it relevant if the work requested clearly "
    "falls within the business's trade. A plumber should NOT match a request "
    "for a house cleaner. Return a score from 0 (irrelevant) to 1 (a strong, "
    "in-field lead) and a one-sentence reason."
)


@dataclass
class MatchResult:
    is_relevant: bool
    score: float
    reason: str


def classify_lead(
    *, post_content: str, trade: str | None, service_categories: list[str]
) -> MatchResult:
    trade_label = trade or "general handyman services"
    categories = ", ".join(c for c in service_categories if c) or trade_label

    ai = get_ai()
    if ai.enabled:
        prompt = (
            f"Business trade: {trade_label}\n"
            f"Service categories: {categories}\n\n"
            f"Community post:\n\"\"\"\n{post_content}\n\"\"\"\n\n"
            "Is this post a genuine lead for this business?"
        )
        result = ai.complete_json(
            system=_SYSTEM,
            prompt=prompt,
            schema=_MATCH_SCHEMA,
            model=settings.leadpilot_ai_classifier_model,
            max_tokens=400,
        )
        if result is not None:
            score = float(result.get("score", 0.0))
            return MatchResult(
                is_relevant=bool(result.get("is_relevant"))
                and score >= RELEVANCE_THRESHOLD,
                score=score,
                reason=str(result.get("reason", "")).strip(),
            )

    return _keyword_fallback(post_content, trade_label, service_categories)


_STOPWORDS = {"and", "the", "for", "with", "services", "service", "general"}


def _stems(phrase: str) -> set[str]:
    """Crude stems (first 5 chars of each significant word) so that e.g.
    'plumbing' and 'plumber' both reduce to 'plumb'.
    """
    out: set[str] = set()
    for word in phrase.lower().replace(",", " ").split():
        word = "".join(ch for ch in word if ch.isalpha())
        if len(word) > 3 and word not in _STOPWORDS:
            out.add(word[:5])
    return out


def _keyword_fallback(
    post_content: str, trade_label: str, service_categories: list[str]
) -> MatchResult:
    text = post_content.lower()
    trade_stems = _stems(trade_label)
    category_stems: set[str] = set()
    for cat in service_categories:
        category_stems |= _stems(cat)

    trade_hit = next((s for s in trade_stems if s in text), None)
    cat_hits = sorted(s for s in category_stems if s not in trade_stems and s in text)

    # The trade itself is the strongest signal; require it, or several
    # category matches, before calling a post in-field.
    if trade_hit:
        score, relevant = 0.85, True
        reason = f"Mentions the client's trade ('{trade_hit}…')."
    elif len(cat_hits) >= 2:
        score, relevant = 0.65, True
        reason = f"Matched service categories: {', '.join(cat_hits[:3])}."
    elif len(cat_hits) == 1:
        score, relevant = 0.4, False
        reason = "Only a weak, single-keyword overlap with the client's trade."
    else:
        score, relevant = 0.0, False
        reason = "No clear overlap with the client's trade or service categories."
    return MatchResult(is_relevant=relevant, score=score, reason=reason)
