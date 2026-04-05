"""Metrics used by the RAG evaluation framework.

Provides: faithfulness_score, relevancy_score, context_precision, context_recall, answer_similarity
"""
from typing import Iterable, Set
from difflib import SequenceMatcher


def _safe_set(iterable: Iterable) -> Set:
    return set(iterable) if iterable is not None else set()


def answer_similarity(a: str, b: str) -> float:
    """Return a normalized similarity [0..1] between two answers.

    Uses SequenceMatcher for character-level similarity and a token-overlap
    fallback for long or repetitive texts. Returns the max of the two heuristics.
    """
    if a is None or b is None:
        return 0.0
    a_s = str(a).strip().lower()
    b_s = str(b).strip().lower()
    if not a_s and not b_s:
        return 1.0
    try:
        seq = SequenceMatcher(None, a_s, b_s).ratio()
    except Exception:
        seq = 0.0
    # token overlap heuristic (Jaccard-like) for long or repetitive strings
    try:
        a_tokens = set(a_s.split())
        b_tokens = set(b_s.split())
        if not a_tokens and not b_tokens:
            tok = 1.0
        elif not a_tokens or not b_tokens:
            tok = 0.0
        else:
            inter = a_tokens & b_tokens
            tok = (2 * len(inter)) / (len(a_tokens) + len(b_tokens))
    except Exception:
        tok = 0.0
    # also consider character n-gram overlap for highly repetitive texts
    try:
        def ngrams(s, n=4):
            return set(s[i:i+n] for i in range(max(0, len(s)-n+1)))
        n1 = ngrams(a_s, 4)
        n2 = ngrams(b_s, 4)
        if n1 or n2:
            inter = n1 & n2
            ngram = (2 * len(inter)) / (len(n1) + len(n2)) if (len(n1) + len(n2)) > 0 else 0.0
        else:
            ngram = 0.0
    except Exception:
        ngram = 0.0
    return max(seq, tok, ngram)


def context_precision(retrieved: Iterable, gold: Iterable) -> float:
    # Count duplicates in retrieved: precision = (# retrieved that are in gold) / (total retrieved)
    r_list = list(retrieved or [])
    g_set = _safe_set(gold)
    if not r_list:
        return 0.0
    tp = sum(1 for doc in r_list if doc in g_set)
    return tp / len(r_list)


def context_recall(retrieved: Iterable, gold: Iterable) -> float:
    r = _safe_set(retrieved)
    g = _safe_set(gold)
    if not g:
        return 0.0
    tp = len(r & g)
    return tp / len(g)


def relevancy_score(retrieved_scores: Iterable[float]) -> float:
    """Compute a simple relevancy score as mean of provided per-doc relevancy scores.

    If no scores provided, return 0.0
    """
    scores = [float(s) for s in (retrieved_scores or [])]
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def faithfulness_score(answer: str, supporting_contexts: Iterable[str], gold_answer: str) -> float:
    """Estimate faithfulness by measuring how similar the answer is to the gold answer
    when supported contexts are provided.

    This is a heuristic: combine answer similarity with whether supporting_contexts are non-empty.
    Returns a float in [0,1].
    """
    sim = answer_similarity(answer, gold_answer)
    support_present = 1.0 if supporting_contexts else 0.0
    # Weighted combination: favor similarity but require some support
    return 0.7 * sim + 0.3 * support_present
