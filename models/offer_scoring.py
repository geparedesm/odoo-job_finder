"""Deterministic scoring with explicit eligibility statements and AI review hints."""

import re


CITIZENSHIP_REASON = "Australian citizenship or permanent residency required"
LEVEL = r"(?:baseline|nv1|nv2|negative\s+vetting\s+[12]|pv|positive\s+vetting)"
REQ = r"(?:is\s+)?(?:required|mandatory|essential)"
ART = r"(?:an?\s+)?"
STATE = r"(?:(?:current|active|valid)\s+)?"
NEGATION = re.compile(r"\b(?:not|no|without|don['’]t|doesn['’]t|isn['’]t|aren['’]t|never)\b", re.I)
OPTIONAL_MARKER = re.compile(
    r"\b(?:desirable|preferred|advantage|advantageous|nice\s+to\s+have|bonus|highly\s+regarded|optional)\b", re.I)
WORK_RIGHTS_ALTERNATIVE = re.compile(
    r"\bor\b(?:\s+\S+){0,5}?\s+(?:visa|work\s+rights|working\s+rights|right\s+to\s+work)\b", re.I)


def _patterns(*expressions):
    return tuple(re.compile(r"\b(?:" + expression + r")\b", re.I) for expression in expressions)


CITIZENSHIP_PATTERNS = _patterns(
    r"must\s+be\s+(?:an\s+australian\s+citizen|australian\s+citizens)",
    r"must\s+be\s+an\s+australian\s+citizen\s+or\s+permanent\s+resident",
    r"must\s+be\s+an\s+australian\s+permanent\s+resident",
    r"must\s+(?:have|hold)\s+australian\s+citizenship",
    r"must\s+(?:have|hold)\s+(?:australian\s+)?permanent\s+residency",
    rf"australian\s+citizenship\s+{REQ}",
    rf"australian\s+citizenship\s+or\s+permanent\s+residency\s+{REQ}",
    rf"permanent\s+residency\s+{REQ}",
    r"australian\s+citizens\s+only|only\s+australian\s+citizens",
)
CLEARANCE_PATTERNS = _patterns(
    rf"must\s+(?:hold|have)\s+{ART}{STATE}{LEVEL}\s+(?:security\s+)?clearance",
    rf"must\s+(?:hold|have)\s+{ART}{STATE}security\s+clearance",
    rf"{LEVEL}\s+(?:security\s+)?clearance\s+{REQ}",
    rf"security\s+clearance\s+{REQ}",
    rf"must\s+be\s+eligible\s+(?:to\s+obtain|for)\s+{ART}(?:{LEVEL}\s+)?(?:security\s+)?clearance",
    rf"must\s+be\s+able\s+to\s+obtain\s+{ART}(?:{LEVEL}\s+)?(?:security\s+)?clearance",
)
MENTION = re.compile(
    rf"\b(?:citizens?|citizenship|permanent\s+(?:residents?|residency|residence)|clearance|{LEVEL})\b", re.I)


def _sentences(text):
    return re.split(r"[.;!?\n\r]+", text)


def eligibility_reason(text):
    """Discard only the explicit statements, with sentence-wide exceptions."""
    for sentence in _sentences(text):
        if NEGATION.search(sentence) or OPTIONAL_MARKER.search(sentence):
            continue
        if any(pattern.search(sentence) for pattern in CLEARANCE_PATTERNS):
            return "Security clearance required"
        if (any(pattern.search(sentence) for pattern in CITIZENSHIP_PATTERNS)
                and not WORK_RIGHTS_ALTERNATIVE.search(sentence)):
            return CITIZENSHIP_REASON
    return ""


def eligibility_mention(text):
    """Flag eligibility vocabulary for AI review; bare PR is not residency."""
    return bool(MENTION.search(text))


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
