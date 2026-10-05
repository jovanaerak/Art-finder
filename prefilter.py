"""
Pre-filtering utilities: cheaply decide whether a scraped page is worth sending
to the (slow) local AI at all, based on dates found via regex, and pull out the
most date/deadline-relevant chunk of the page so the AI isn't blindly fed the
first N characters (which is often nav/header junk).
"""

import re
from datetime import datetime

import dateparser  # pip install dateparser

TODAY = datetime.now()

# Keywords that tend to sit near the actual deadline/eligibility info.
# Used to find the most relevant *window* of text on a long page.
RELEVANT_KEYWORDS = [
    "deadline", "due date", "due by", "submit by", "entries close",
    "entry deadline", "submission deadline", "postmarked by",
    "must be received", "closes", "opens", "eligibility", "entry fee",
]

# Broad date-shaped patterns. Not exhaustive, but covers the common written forms:
# "March 1, 2027", "3/1/2027", "1/31/26", "October 31", "2026-10-18"
DATE_PATTERNS = [
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s*\d{2,4}?\b",
    r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
    r"\b\d{4}-\d{2}-\d{2}\b",
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}\b",
]

_DATE_RE = re.compile("|".join(DATE_PATTERNS), re.IGNORECASE)

# Catches a bare 4-digit year, e.g. "2024", even with no month/day attached.
# Used to flag pages whose ONLY year references are stale (e.g. "Hudgens Prize 2024")
# even when no full date pattern (the regexes above) is present.
_YEAR_RE = re.compile(r"\b20\d{2}\b")


def find_years(text: str):
    """Return every bare 4-digit year mentioned in text, as ints."""
    return [int(y) for y in _YEAR_RE.findall(text)]


def find_dates(text: str):
    """Return a list of (raw_text, parsed_datetime_or_None) for every date-like
    substring found in text."""
    found = []
    for match in _DATE_RE.finditer(text):
        raw = match.group(0)
        parsed = dateparser.parse(raw, settings={"PREFER_DATES_FROM": "future"})
        found.append((raw, parsed))
    return found


def classify_page(text: str):
    """
    Decide whether a page is worth sending to the AI.

    Returns one of:
      "future_deadline"    - at least one full date found that is today or later -> definitely analyze
      "no_date_found"      - no date-shaped text and no year references at all -> still analyze
      "only_past_dates"    - every full date found is in the past -> skip, almost certainly expired
      "likely_stale_year"  - no full date found, but every bare year mentioned (e.g. in a title
                              like "Hudgens Prize 2024") is in the past -> skip, likely an old page
    """
    dates = find_dates(text)
    parsed_dates = [d for _, d in dates if d is not None]

    if parsed_dates:
        if any(d >= TODAY for d in parsed_dates):
            return "future_deadline", dates
        return "only_past_dates", dates

    # No full date pattern matched. Fall back to checking bare years
    # (catches "Hudgens Prize 2024" style titles with no month/day attached).
    years = find_years(text)
    if years:
        current_year = TODAY.year
        if all(y < current_year for y in years):
            return "likely_stale_year", dates
        return "no_date_found", dates

    return "no_date_found", dates


def qualifies_for_ai(classification: str) -> bool:
    """
    The single gate deciding whether a page is worth the AI's time.
    Only pages where we found an actual, parseable, future-dated deadline
    qualify -- "no_date_found" pages used to be sent through "just in case",
    but in practice they were mostly noise (irrelevant pages, wrong section
    of a site, etc.) and not worth the AI cost. Tighten this here if that
    turns out to be too strict for your use case.
    """
    return classification == "future_deadline"


def looks_like_a_date(deadline_text: str) -> bool:
    """
    Sanity check on what the AI returned for the deadline field. Even with a
    tightened prompt, a small local model will sometimes still paraphrase
    ("3 days prior to the Saturday department deadline") instead of giving a
    clean date. This flags those so they can be treated differently downstream
    (e.g. shown to the user as 'needs manual check' rather than trusted as-is).
    """
    if deadline_text.strip().lower() == "not specified":
        return True
    return bool(_DATE_RE.search(deadline_text)) or bool(_YEAR_RE.search(deadline_text))


def build_focused_context(text: str, window_chars: int = 800, max_total_chars: int = 6000) -> str:
    """
    Instead of blindly truncating from the top, find windows of text around
    deadline/eligibility keywords and prioritize those, falling back to the
    start of the page to fill any remaining budget.
    """
    lower_text = text.lower()
    windows = []

    for kw in RELEVANT_KEYWORDS:
        idx = lower_text.find(kw)
        while idx != -1:
            start = max(0, idx - window_chars // 2)
            end = min(len(text), idx + window_chars // 2)
            windows.append((start, end))
            idx = lower_text.find(kw, idx + 1)

    # Merge overlapping windows so we don't duplicate text
    windows.sort()
    merged = []
    for start, end in windows:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    focused_chunks = [text[start:end] for start, end in merged]
    focused_text = "\n...\n".join(focused_chunks)

    if len(focused_text) >= max_total_chars:
        return focused_text[:max_total_chars]

    # Fill remaining budget with the top of the page (covers titles, general
    # program info that keyword windows might miss).
    remaining_budget = max_total_chars - len(focused_text)
    leading_text = text[:remaining_budget]

    if focused_text:
        return leading_text + "\n...\n" + focused_text
    return leading_text