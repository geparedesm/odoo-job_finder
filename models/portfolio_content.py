"""Small text helpers for the public portfolio, without Odoo."""

import re
from typing import Optional


def safe_url(value: Optional[str]) -> Optional[str]:
    """
    Validate and normalize a URL. Returns None if not a safe http(s) URL.
    Adds https:// to bare domain names like 'linkedin.com/in/x'.
    """
    if not value:
        return None
    value = value.strip()
    if not value or " " in value:
        return None
    # Reject javascript: and other non-http schemes
    if re.match(r"^\w+:", value) and not re.match(r"^https?:", value, re.IGNORECASE):
        return None
    if not re.match(r"^https?://", value, re.IGNORECASE):
        if "." not in value:
            return None
        value = "https://" + value
    return value


def capitalize_first(text: Optional[str]) -> str:
    """'music social application' -> 'Music social application'; the rest is kept as written."""
    text = (text or "").strip()
    return text[:1].upper() + text[1:]


def headline_parts(headline: Optional[str]) -> list[str]:
    """'SOFTWARE DEVELOPMENT | ICT | MECHATRONICS' -> ['Software development', 'ICT', 'Mechatronics'].

    Parts written in capitals become sentence case, except short acronyms (four letters or fewer).
    """
    parts = []
    for part in (headline or "").split("|"):
        part = " ".join(part.split())
        if not part:
            continue
        if part.isupper() and len(part.replace(" ", "")) > 4:
            part = part[:1] + part[1:].lower()
        parts.append(part)
    return parts


def paragraphs(text: Optional[str]) -> list[str]:
    """Single line breaks are joined (PDF wrapping); blank lines start a new paragraph."""
    blocks = re.split(r"\n\s*\n", (text or "").strip())
    return [" ".join(block.split()) for block in blocks if block.strip()]


def first_sentence(text: Optional[str]) -> str:
    """The first sentence of a text ('Built pipelines. Added tests.' -> 'Built pipelines.')."""
    text = " ".join((text or "").split())
    match = re.search(r"^(.+?[.!?])(?=\s+[A-Z(])", text)
    return match.group(1) if match else text


def en_dash_ranges(text: Optional[str]) -> str:
    """'2015 - 2021' -> '2015 – 2021' (number ranges only)."""
    return re.sub(r"(\d)\s+-\s+(\d)", "\\1 – \\2", text or "")


def split_organisation(company: Optional[str]) -> tuple[str, str]:
    """'Intelligent Systems Research Group, Universidad Técnica del Norte' -> (organisation, group)."""
    group, sep, organisation = (company or "").rpartition(", ")
    return (organisation, group) if sep and group and organisation else (company or "", "")


def highlight_lines(text: Optional[str]) -> list[str]:
    """Non-empty lines of a highlights field, without leading bullets."""
    lines = (line.strip().lstrip("•-*").strip() for line in (text or "").splitlines())
    return [line for line in lines if line]
