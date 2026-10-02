"""Parse plain CV text without requiring Odoo or third-party packages."""

import re


_FIELDS = (
    "full_name", "headline", "email", "phone", "location", "linkedin",
    "summary", "skills", "experience", "education", "certifications", "languages",
)
_SECTIONS = {
    "skills": "skills",
    "summary": "summary",
    "profile": "summary",
    "personalattributes": "summary",
    "professionalexperience": "experience",
    "experience": "experience",
    "workexperience": "experience",
    "education": "education",
    "certification": "certifications",
    "certifications": "certifications",
    "languages": "languages",
}
_BOUNDARIES = {"references", "leadership&volunteeringexperience"}
_EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}")
_LINKEDIN = re.compile(
    r"(?:https?://)?(?:www\.)?linkedin\.com/(?:in|pub)/[^\s•|,;]+",
    re.IGNORECASE,
)
_PHONE = re.compile(r"(?<!\w)(?:\(\+?\d{1,4}\)|\+?\d)[\d ().-]*\d(?!\w)")


def _heading(line):
    # PDF text extraction can omit spaces between words in condensed headings.
    return "".join(line.rstrip(":").split()).casefold()


def parse_cv_text(text: str) -> dict:
    """Return string fields; text without a recognized section returns blanks.

    Contact details are taken only from the first ten nonempty lines before
    the first section. Section bodies retain their line breaks and bullets.
    Repeated sections are combined in document order.
    """
    result = dict.fromkeys(_FIELDS, "")
    if not isinstance(text, str) or not text.strip():
        return result

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    first_section = next(
        (i for i, line in enumerate(lines) if _heading(line) in _SECTIONS),
        None,
    )
    if first_section is None:
        return result

    header = lines[:first_section]
    if header:
        result["full_name"] = header[0]
    if len(header) > 1:
        title = header[1]
        if len(title) <= 100 and "@" not in title and not re.search(r"\d", title):
            result["headline"] = title

    contact = "\n".join(header[:10])
    for field, pattern in (("email", _EMAIL), ("linkedin", _LINKEDIN)):
        match = pattern.search(contact)
        if match:
            result[field] = match.group().rstrip(".)")
    for match in _PHONE.finditer(contact):
        candidate = match.group().strip()
        if 7 <= len(re.sub(r"\D", "", candidate)) <= 15:
            result["phone"] = candidate
            break

    # The sample CV puts the location first on a bullet-separated contact line.
    for line in header[:10]:
        if "•" in line or "|" in line:
            candidate = re.split(r"[•|]", line)[0].strip()
            if candidate and not any(
                pattern.search(candidate) for pattern in (_EMAIL, _PHONE, _LINKEDIN)
            ):
                result["location"] = candidate
                break

    bodies = {field: [] for field in set(_SECTIONS.values())}
    active = None
    for line in lines[first_section:]:
        heading = _heading(line)
        if heading in _SECTIONS:
            active = _SECTIONS[heading]
        elif heading in _BOUNDARIES:
            active = None
        elif active:
            bodies[active].append(line)
    for field, body in bodies.items():
        result[field] = "\n".join(body)
    return result
