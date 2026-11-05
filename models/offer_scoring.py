"""Deterministic snippet scoring; ambiguous eligibility is retained for review."""

import re


SUBJECTS = (
    (r"(?:australian\s+citizen(?:ship|s)?|citizenship)", "Australian citizenship required"),
    (r"(?:permanent\s+residen(?:t[s]?|cy|ce)|\bpr\b)", "Permanent residency required"),
    (r"(?:(?:baseline|nv1|nv2)\s+)?(?:security\s+)?clearance", "Security clearance required"),
)


def eligibility_reason(text):
    """Match obligations next to their subject; unrelated negations cannot erase them."""
    clauses = re.split(r"[.;!?\n]|\b(?:but|however|although|and)\b", text.lower())
    before_requirement = re.compile(
        r"(?:\b(?:must|shall|should|need to|needs to|required to)\s+"
        r"(?:(?:be|an?|the|eligible|for|hold|obtain|maintain|have|possess|current|valid|active)\s+){0,8}"
        r"|\b(?:only|requires?|mandatory|essential|required)\s+(?:an?\s+)?)$"
    )
    after_requirement = re.compile(
        r"^\s*(?:(?:is|are|will be)\s+)?(?:(?:strictly|a|an)\s+)?"
        r"(?:required|mandatory|essential|requirement|only)\b"
    )
    for clause in clauses:
        for subject, reason in SUBJECTS:
            for match in re.finditer(subject, clause):
                before, after = clause[:match.start()], clause[match.end():].split(",", 1)[0]
                prefix_match = before_requirement.search(before)
                suffix_match = after_requirement.search(after)
                if not prefix_match and not suffix_match:
                    continue
                if re.search(r"\b(?:no|without)\s+(?:an?\s+)?$", before):
                    continue
                if prefix_match and re.search(r"\b(?:not|never)\s+$", before[:prefix_match.start()]):
                    continue
                if re.match(r"^.{0,25}\b(?:not required|not a requirement|optional|desirable|preferred)\b", after):
                    continue
                if reason != "Security clearance required" and re.search(
                    r"visa\s+holders?|work(?:ing)?\s+rights", clause
                ):
                    continue
                return reason
    return ""


def score_offer(title, snippet, area_terms, technologies, location, target="Perth"):
    """Return score, additive components and an English reason key for translation."""
    text = f"{title} {snippet}".lower()
    reason = eligibility_reason(text)
    if re.search(r"\b(senior|lead|principal|head|manager|architect)\b", title.lower()):
        reason = "Excluded seniority"
    if reason:
        return 0, dict.fromkeys(("area", "technologies", "seniority", "location", "sponsorship"), 0), reason
    parts = {
        "area": 30 if any(term.lower() in title.lower() for term in area_terms if term) else 0,
        "technologies": min(38, sum(weight for name, weight in technologies.items()
                                   if re.search(r"(?<!\w)" + re.escape(name.lower()) + r"(?!\w)", text))),
        "seniority": 15 if re.search(r"\b(junior|graduate|entry[ -]level)\b", title.lower()) else 0,
        "location": 10 if target.lower() in location.lower() or "remote" in text else 0,
        "sponsorship": 7 if re.search(r"visa\s+sponsorship", text) else 0,
    }
    return sum(parts.values()), parts, ""


def usage_years(intervals):
    """Union of known closed usage intervals; callers resolve genuinely current roles."""
    merged = []
    for start, end in sorted((a, b) for a, b in intervals if a and b and b >= a):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return round(sum((end - start).days for start, end in merged) / 365.25, 2)
