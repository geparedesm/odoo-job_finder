"""Score and rank plain job posting text without Odoo or external packages."""

import re


_PROFILE_FIELDS = ("skills", "experience", "summary")
_KEYWORD = re.compile(r"\w+")


def _keywords(text):
    """Return distinct case-insensitive words, treating punctuation as separators."""
    if not isinstance(text, str):
        return set()
    return set(_KEYWORD.findall(text.casefold()))


def _profile_keywords(profile):
    keywords = set()
    for field in _PROFILE_FIELDS:
        keywords.update(_keywords(profile.get(field, "")))
    return keywords


def score_job(profile: dict, posting_text: str) -> int:
    """Count distinct shared words in profile fields and posting title/description.

    Combine a posting's title and description into posting_text before calling.
    Missing or blank profile fields contribute no keywords. Repetition does not
    increase the score, and partial words do not match.
    """
    return len(_profile_keywords(profile) & _keywords(posting_text))


def rank_jobs(profile: dict, posting_texts) -> list:
    """Return (posting_text, score) pairs, highest first and stable for ties.

    All input postings are retained, including duplicates and zero-score matches.
    """
    keywords = _profile_keywords(profile)
    scored = [
        (posting, len(keywords & _keywords(posting)))
        for posting in posting_texts
    ]
    return sorted(scored, key=lambda pair: pair[1], reverse=True)
