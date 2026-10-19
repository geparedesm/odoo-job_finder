"""Portfolio content parsing: splits free-form text fields into structured data."""

import re
from typing import Any, Optional


def split_blocks(text: Optional[str]) -> list[str]:
    """Split text by blank lines (blocks separated by double newlines)."""
    if not text:
        return []
    blocks = re.split(r"\n\s*\n+", text.strip())
    return [block.strip() for block in blocks if block.strip()]


def split_items(text: Optional[str]) -> list[str]:
    """Split text into items: lines, bullets, or semicolon-separated."""
    if not text:
        return []
    # Remove bullet points/dashes and normalize
    text = text.strip()
    items = []

    # Try bullet/dash separated first (lines starting with -, •, *)
    if re.search(r"^\s*[-•*]", text, re.MULTILINE):
        # Split by bullets and filter out empty strings
        parts = re.split(r"[-•*]", text)
        items = [part.strip() for part in parts if part.strip()]
    # Otherwise split by newlines
    elif "\n" in text:
        items = [item.strip() for item in text.split("\n") if item.strip()]
    # Otherwise split by semicolon or comma
    elif ";" in text:
        items = [item.strip() for item in text.split(";") if item.strip()]
    elif "," in text:
        items = [item.strip() for item in text.split(",") if item.strip()]
    else:
        items = [text]

    return items


def parse_entries(text: Optional[str]) -> list[dict[str, Any]]:
    """
    Parse experience/education/projects into entries.
    Each block is one entry: first line is title, second line is date/location, rest is details.
    """
    if not text:
        return []
    blocks = split_blocks(text)
    entries = []

    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue
        entry = {"title": lines[0] if lines else ""}
        if len(lines) > 1:
            entry["subtitle"] = lines[1]
        if len(lines) > 2:
            entry["details"] = "\n".join(lines[2:])
        entries.append(entry)

    return entries


def safe_url(value: Optional[str]) -> Optional[str]:
    """
    Validate and normalize a URL. Returns None if not a safe http(s) URL.
    Adds https:// to bare domain names like 'linkedin.com/in/x'.
    """
    if not value:
        return None
    value = value.strip()
    if not value:
        return None

    # Reject URLs with spaces
    if " " in value:
        return None

    # Reject javascript: and other non-http schemes
    if re.match(r"^\w+:", value) and not re.match(r"^https?:", value, re.IGNORECASE):
        return None

    # If it looks like a domain without scheme, add https://
    if not re.match(r"^https?://", value, re.IGNORECASE):
        # Check if it looks like a domain (has a dot)
        if "." in value:
            value = "https://" + value
        else:
            return None

    return value
