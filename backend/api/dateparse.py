"""Parse dates the way they are written in a paper khata (day-first, usually no year).

parse_date_text("21 Sep")  -> date(<this year>, 9, 21)
parse_date_text("12/10")   -> 12 October (day first, Indian convention)
parse_date_text("nonsense") -> None
"""
import re
from datetime import date, timedelta

from django.utils import timezone

# If an assumed-year date lands more than this many days in the future, use last year.
FUTURE_TOLERANCE_DAYS = 7

_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
_FULL_MONTHS = ["january", "february", "march", "april", "may", "june", "july",
                "august", "september", "october", "november", "december"]

_YEAR = r"(\d{4}|\d{2})"
_ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
_NUMERIC = re.compile(rf"^(\d{{1,2}})\s*[/\-.]\s*(\d{{1,2}})(?:\s*[/\-.]\s*{_YEAR})?$")
_DAY_MONTHNAME = re.compile(rf"^(\d{{1,2}})[\s\-./]*([A-Za-z]+)\.?(?:[\s,\-./]*{_YEAR})?$")
_MONTHNAME_DAY = re.compile(rf"^([A-Za-z]+)\.?[\s\-./]*(\d{{1,2}})(?!\d)(?:[\s,\-./]*{_YEAR})?$")
_ORDINAL = re.compile(r"(?<=\d)(st|nd|rd|th)\b", re.IGNORECASE)


def _month_number(word: str) -> int | None:
    w = word.lower().rstrip(".")
    if w == "sept":
        return 9
    if len(w) < 3:
        return None
    for i, full in enumerate(_FULL_MONTHS, start=1):
        if full.startswith(w):
            return i
    return None


def _year(text: str | None) -> int | None:
    if text is None:
        return None
    y = int(text)
    return 2000 + y if y < 100 else y


def _build(day: int, month: int, year: int | None, today: date) -> date | None:
    if year is not None:
        try:
            return date(year, month, day)
        except ValueError:
            return None
    # No year written: assume this year, but a date far in the future means last year.
    for candidate_year in (today.year, today.year - 1):
        try:
            d = date(candidate_year, month, day)
        except ValueError:
            continue  # e.g. 29 Feb in a non-leap year
        if d <= today + timedelta(days=FUTURE_TOLERANCE_DAYS):
            return d
        # too far ahead: loop falls through to last year
    return None


def parse_date_text(text: str | None, today: date | None = None) -> date | None:
    """Return a date, or None if the text cannot be understood."""
    if not text:
        return None
    today = today or timezone.localdate()
    s = text.translate(_DEVANAGARI_DIGITS).strip()
    s = _ORDINAL.sub("", s)
    s = re.sub(r"\s+", " ", s).strip(" ,")
    if not s:
        return None

    m = _ISO.match(s)
    if m:
        return _build(int(m[3]), int(m[2]), int(m[1]), today)

    m = _NUMERIC.match(s)
    if m:
        return _build(int(m[1]), int(m[2]), _year(m[3]), today)

    m = _DAY_MONTHNAME.match(s)
    if m:
        month = _month_number(m[2])
        if month:
            return _build(int(m[1]), month, _year(m[3]), today)
        return None

    m = _MONTHNAME_DAY.match(s)
    if m:
        month = _month_number(m[1])
        if month:
            return _build(int(m[2]), month, _year(m[3]), today)
        return None

    return None
