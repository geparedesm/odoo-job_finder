"""Portfolio content parsing: splits free-form text fields into structured data."""

import re
from typing import Any, Optional

BULLET = re.compile(r"^\s*[-•*]\s*")


def split_lines(text: Optional[str]) -> list[str]:
    """Return non-empty stripped lines, with leading bullets (•, -, *) removed."""
    if not text:
        return []
    lines = (BULLET.sub("", line).strip() for line in text.splitlines())
    return [line for line in lines if line]


def split_blocks(text: Optional[str]) -> list[dict[str, Any]]:
    """Split text on blank lines into blocks of {title: first line, lines: the rest}."""
    if not text or not text.strip():
        return []
    blocks = []
    for chunk in re.split(r"\n\s*\n", text.strip()):
        lines = split_lines(chunk)
        if lines:
            blocks.append({"title": lines[0], "lines": lines[1:]})
    return blocks


def split_items(text: Optional[str]) -> list[str]:
    """Split text into items: one per line, otherwise semicolon- or comma-separated."""
    if not text or not text.strip():
        return []
    lines = split_lines(text)
    if len(lines) > 1:
        return lines
    line = lines[0]
    for separator in (";", ","):
        if separator in line:
            return [item.strip() for item in line.split(separator) if item.strip()]
    return [line]


def parse_entries(text: Optional[str]) -> list[dict[str, Any]]:
    """
    Parse experience/education/projects into entries.
    Each block is one entry: first line is title, second line is date/location, rest is details.
    """
    entries = []
    for block in split_blocks(text):
        entry = {"title": block["title"]}
        if block["lines"]:
            entry["subtitle"] = block["lines"][0]
        if len(block["lines"]) > 1:
            entry["details"] = "\n".join(block["lines"][1:])
        entries.append(entry)
    return entries


def normalize_host(host: Optional[str]) -> str:
    """Lowercase a request host and strip its port."""
    host = (host or "").strip().lower()
    if host.startswith("["):  # IPv6 literal, e.g. [::1]:8069
        return host.split("]")[0] + "]"
    return host.split(":")[0]


def parse_hosts(value: Optional[str]) -> set[str]:
    """Parse a comma-separated host list into a lowercase set without whitespace."""
    return {host.strip().lower() for host in (value or "").split(",") if host.strip()}


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
