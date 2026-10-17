"""Parse plain CV text without requiring Odoo or third-party packages."""

import re


_FIELDS = (
    "full_name", "headline", "email", "phone", "location", "linkedin", "website", "github",
    "summary", "skills", "experience", "education", "languages",
    "volunteering", "projects", "trainings",
)
_SECTIONS = {
    "technicalskills": "skills",
    "professionalprofile": "summary",
    "academicresearch": "projects",
    "academicprojects": "projects",
    "leadershipandvolunteering": "volunteering",
    "leadership&volunteeringexperience": "volunteering",
    "trainingandcredentials": "trainings",
    "skills": "skills",
    "summary": "summary",
    "profile": "summary",
    "personalattributes": "summary",
    "professionalexperience": "experience",
    "experience": "experience",
    "workexperience": "experience",
    "education": "education",
    "languages": "languages",
    "language": "languages",
}
_BOUNDARIES = {"references", "certification", "certifications"}
_EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}")
_LINKEDIN = re.compile(
    r"(?:https?://)?(?:www\.)?linkedin\.com/(?:in|pub)/[^\s•|,;]+",
    re.IGNORECASE,
)
_GITHUB = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/[^\s•|,;]+",
    re.IGNORECASE,
)
_WEBSITE = re.compile(
    r"(?<![\w.@/-])(?:https?://)?(?:www\.)?"
    r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+"
    r"[a-zA-Z]{2,}(?:/[^\s•|,;]*)?",
    re.IGNORECASE,
)
_PHONE = re.compile(r"(?<!\w)(?:\(\+?\d{1,4}\)|\+?\d)[\d ().-]*\d(?!\w)")


def _heading(line):
    # PDF text extraction can omit spaces between words in condensed headings.
    base = re.split(r"\s+[-–—]\s+", line, maxsplit=1)[0]
    return "".join(base.rstrip(":").split()).casefold()


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
    excluded_spans = [
        match.span()
        for pattern in (_EMAIL, _LINKEDIN, _GITHUB)
        for match in pattern.finditer(contact)
    ]
    email_domains = {match.group().split("@")[1].casefold() for match in _EMAIL.finditer(contact)}
    for field, pattern in (
        ("email", _EMAIL), ("linkedin", _LINKEDIN), ("github", _GITHUB),
        ("website", _WEBSITE),
    ):
        for match in pattern.finditer(contact):
            if field == "website":
                domain = re.sub(r"^https?://", "", match.group(), flags=re.IGNORECASE)
                domain = domain.split("/")[0].casefold().removeprefix("www.")
                if (any(start < match.end() and match.start() < end for start, end in excluded_spans)
                        or domain in email_domains or domain in ("linkedin.com", "github.com")):
                    continue
            result[field] = match.group().rstrip(".)")
            break
    for match in _PHONE.finditer(contact):
        candidate = match.group().strip()
        if 7 <= len(re.sub(r"\D", "", candidate)) <= 15:
            result["phone"] = candidate
            break

    # Location comes first on a delimited contact line, not a topic headline.
    for line in header[:10]:
        if ("•" in line or "|" in line) and any(
            pattern.search(line) for pattern in (_EMAIL, _PHONE, _LINKEDIN)
        ):
            candidate = re.split(r"[•|]", line)[0].strip()
            if candidate and not any(
                pattern.search(candidate) for pattern in (_EMAIL, _PHONE, _LINKEDIN)
            ):
                result["location"] = candidate
                break

    bodies = {field: [] for field in set(_SECTIONS.values())}
    active = None
    full_name = result["full_name"].casefold()
    footer = re.compile(
        rf"^{re.escape(result['full_name'])} +\d+ */ *\d+$", re.IGNORECASE,
    ) if full_name else None
    after_name = False
    for line in lines[first_section:]:
        heading = _heading(line)
        is_boundary = heading in _SECTIONS or heading in _BOUNDARIES
        if not is_boundary and full_name:
            if line.casefold() == full_name:
                after_name = True
                continue
            if footer.fullmatch(line):
                after_name = False
                continue
            if after_name:
                after_name = False
                # Some PDF extractors put the footer's page count on its own line.
                if re.fullmatch(r"\d+ */ *\d+", line) or line.casefold() in {
                    result["headline"].casefold(), "professional cv", "career overview",
                }:
                    continue
        after_name = False
        if heading in _SECTIONS:
            active = _SECTIONS[heading]
        elif heading in _BOUNDARIES:
            active = None
        elif active:
            spoken = re.fullmatch(r"Languages spoken:\s*(.+)", line, re.IGNORECASE)
            if active == "skills" and spoken:
                bodies["languages"].append(spoken.group(1))
            else:
                bodies[active].append(line)
    for field, body in bodies.items():
        result[field] = "\n".join(body)
    return result
