"""Deterministic snippet scoring; ambiguous eligibility is retained for review."""

import re


CITIZENSHIP_REASON = "Australian citizenship or permanent residency required"
CLEARANCE = r"\b(?:security\s+clearance|eligible\s+(?:for|to obtain)\s+(?:a\s+)?clearance|agsva\s+clearance|baseline|nv[12]|negative vetting(?:(?: level)? [12])?|pv|positive vetting|tssc)\b"
CITIZENSHIP = r"\b(?:australian\s+citizen(?:ship|s)?|citizenship|permanent\s+residen(?:ts?|cy|ce)|pr)\b"
OBLIGATION = r"\b(?:must|shall|should|requir(?:es|ing|ed)|requirement|needed|necessary|mandatory|essential|needs? to|only|eligible (?:for|to obtain)|able to obtain|ability to obtain|obtain and maintain)\b"
OPTIONAL = r"\b(?:not (?:be )?required|not a requirement|not (?:necessary|needed|mandatory|essential)|requirement (?:does not|doesn't) apply|(?:has been |is )?waived|optional|desirable|advantage(?:ous)?|nice to have|preferred|bonus|highly regarded|previous experience (?:on|with|in))\b"
ALTERNATIVE = (
    r"(?:\bor\b|\balternatively\b|and/or)\s+"
    r"(?:(?:those with|anyone with|have|hold|other|any|valid|a valid|temporary|full|unrestricted)\s+)*"
    r"(?:visa holders?|work(?:ing)? rights|right to work)\b"
)


def _has_work_rights_alternative(requirement):
    """A comma may separate list items, but cannot itself establish an alternative."""
    for alternative in re.finditer(ALTERNATIVE, requirement):
        tail = requirement[alternative.end():]
        if re.match(r"\s+(?:are\s+)?also\s+(?:required|needed|necessary)\b", tail):
            continue
        for subject in re.finditer(CITIZENSHIP, requirement[:alternative.start()]):
            between = requirement[subject.end():alternative.start()]
            between = re.sub(CITIZENSHIP, "", between)
            # Keep only eligibility-list connectors and predicates, never an unrelated requirement.
            between = re.sub(r"\b(?:or|either|is|are|required|needed|necessary|mandatory|essential)\b|[,\s]", "", between)
            if not between:
                return True
    return False


def eligibility_reason(text):
    """Judge independent requirements separately while retaining genuine eligibility alternatives."""
    requirements = re.split(r"[.;!?\n•]|\s+—\s+|\b(?:but|however|although)\b|(?<!obtain )(?<!/)\band\b(?!/)", text.lower())
    for requirement in requirements:
        alternative = _has_work_rights_alternative(requirement)
        for clause in requirement.split(","):
            subjects = [(match, reason) for pattern, reason in
                        ((CLEARANCE, "Security clearance required"), (CITIZENSHIP, CITIZENSHIP_REASON))
                        for match in re.finditer(pattern, clause)]
            if not subjects or not re.search(OBLIGATION, clause):
                continue
            if re.search(OPTIONAL, clause):
                continue
            if re.search(rf"\bno .{{0,30}}(?:{CLEARANCE}|{CITIZENSHIP}|clearance)\s+(?:(?:is|are)\s+)?(?:required|needed|necessary)\b", clause):
                continue
            for _, reason in subjects:
                if reason == CITIZENSHIP_REASON and alternative:
                    continue
                return reason
    return ""


def location_matches(location, target):
    """Match complete normalised city names; Australia and remote are explicit modes."""
    targets = [target] if isinstance(target, str) else target
    def normalise(value):
        return " ".join(re.findall(r"\w+", value.casefold()))
    actual = " " + normalise(location) + " "
    return any(normalise(city) == "australia" or
               (normalise(city) and " " + normalise(city) + " " in actual) for city in targets)


def score_offer(title, snippet, area_terms, technologies, location, target="Perth"):
    """Return score, additive components and an English reason key for translation."""
    text = f"{title} {snippet}".lower()
    reason = eligibility_reason(f"{title}\n{snippet}")
    if re.search(r"\b(senior|lead|principal|head|manager|architect)\b", title.lower()):
        reason = "Excluded seniority"
    if reason:
        return 0, dict.fromkeys(("area", "technologies", "seniority", "location", "sponsorship"), 0), reason
    parts = {
        "area": 30 if any(term.lower() in title.lower() for term in area_terms if term) else 0,
        "technologies": min(38, sum(weight for name, weight in technologies.items()
                                   if re.search(r"(?<!\w)" + re.escape(name.lower()) + r"(?!\w)", text))),
        "seniority": 15 if re.search(r"\b(junior|graduate|entry[ -]level)\b", title.lower()) else 0,
        "location": 10 if location_matches(location, target) or
        ("remote" in ([target] if isinstance(target, str) else target) and re.search(r"\bremote\b", text)) else 0,
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
