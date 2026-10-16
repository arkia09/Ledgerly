"""Fuzzy customer-name matching. Suggests only; never merges."""
import unicodedata

from django.conf import settings
from rapidfuzz import fuzz


def normalize_name(name: str | None) -> str:
    """Casefold, collapse whitespace, NFC-normalise (so Devanagari compares reliably)."""
    if not name:
        return ""
    text = unicodedata.normalize("NFC", name)
    return " ".join(text.split()).casefold()


def suggest_customer(name: str | None, customers, threshold: float | None = None) -> dict | None:
    """customers: iterable of (id, name). Returns {"id", "name", "score"} or None.

    An exact (normalised) match scores 100 and wins. Otherwise the best match at or
    above the threshold is returned. rapidfuzz works on code points, so Devanagari is fine.
    """
    if threshold is None:
        threshold = settings.LEDGERLY_MATCH_THRESHOLD
    key = normalize_name(name)
    if not key:
        return None

    best = None
    best_score = -1.0
    for cid, cname in sorted(customers, key=lambda c: c[0]):
        score = 100.0 if normalize_name(cname) == key else fuzz.ratio(key, normalize_name(cname))
        if score > best_score:
            best, best_score = (cid, cname), score
    if best is None or best_score < threshold:
        return None
    return {"id": best[0], "name": best[1], "score": round(best_score, 1)}
