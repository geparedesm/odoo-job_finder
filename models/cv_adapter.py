"""Adapt plain CV text without requiring Odoo or third-party packages."""

import re


_STOP_WORDS = set(
    "a an and are as at be been being by for from had has have in is it of on "
    "or our that the their this to was were will with i my we you your "
    "experienced experience expertise seeking required desirable built builds".split()
)


def _mentioned(keyword, text):
    """Match whole keywords, including punctuation in skills like C++ or C#."""
    return re.search(
        r"(?<!\w)" + re.escape(keyword) + r"(?!\w)", text, re.IGNORECASE,
    ) is not None


def adapt_profile(fields: dict, job_description: str) -> dict:
    """Return a summary and skills draft, leaving the source fields untouched.

    Matching skills come first, retaining their original order and spelling.
    The summary highlights vocabulary already present in the profile; job-only
    requirements are never added. Empty jobs or no overlap preserve both texts.
    """
    summary = fields.get("summary") or ""
    skills = fields.get("skills") or ""
    result = {"summary": summary, "skills": skills}
    if not isinstance(job_description, str) or not job_description.strip():
        return result

    items = [item.strip() for item in re.split(r"[\n,;•]+", skills) if item.strip()]
    matching = [item for item in items if _mentioned(item, job_description)]
    keywords = list(matching)
    # Experience and summary can supply overlap even without a skills section.
    source = summary + "\n" + (fields.get("experience") or "")
    for word in re.findall(r"[\w]+(?:[+#]+)?", source):
        if (
            len(word) >= 3
            and word.casefold() not in _STOP_WORDS
            and _mentioned(word, job_description)
            and not any(_mentioned(word, keyword) for keyword in keywords)
        ):
            keywords.append(word)

    if not keywords:
        return result
    if matching:
        remaining = [item for item in items if item not in matching]
        result["skills"] = "\n".join(matching + remaining)
    emphasis = "Relevant strengths: " + ", ".join(keywords) + "."
    result["summary"] = emphasis + ("\n\n" + summary if summary else "")
    return result
