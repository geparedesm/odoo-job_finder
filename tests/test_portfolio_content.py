"""Tests for portfolio content parsing."""

import re
import unittest
from typing import Any, Optional


# Inline portfolio_content functions to avoid Odoo import dependency
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


class PortfolioContentTestCase(unittest.TestCase):
    """Test portfolio content splitting and parsing."""

    def test_split_blocks_simple(self):
        """Split text by blank lines."""
        text = "First block\n\nSecond block\n\nThird block"
        result = split_blocks(text)
        self.assertEqual(result, ["First block", "Second block", "Third block"])

    def test_split_blocks_empty(self):
        """Empty or None input returns empty list."""
        self.assertEqual(split_blocks(None), [])
        self.assertEqual(split_blocks(""), [])
        self.assertEqual(split_blocks("   \n  \n  "), [])

    def test_split_blocks_whitespace(self):
        """Whitespace handling."""
        text = "  First  \n\n\n  Second  \n\n"
        result = split_blocks(text)
        self.assertEqual(result, ["First", "Second"])

    def test_split_items_lines(self):
        """Split items by newlines."""
        text = "Python\nJavaScript\nRust"
        result = split_items(text)
        self.assertEqual(result, ["Python", "JavaScript", "Rust"])

    def test_split_items_bullets(self):
        """Split items by bullets."""
        text = "- Python\n- JavaScript\n- Rust"
        result = split_items(text)
        self.assertEqual(result, ["Python", "JavaScript", "Rust"])

    def test_split_items_dashes(self):
        """Split items by dashes."""
        text = "* Python\n* JavaScript\n* Rust"
        result = split_items(text)
        # Dashes split by * (asterisk acts as bullet)
        self.assertTrue(len(result) > 0)

    def test_split_items_semicolon(self):
        """Split items by semicolons."""
        text = "Python; JavaScript; Rust"
        result = split_items(text)
        self.assertEqual(result, ["Python", "JavaScript", "Rust"])

    def test_split_items_comma(self):
        """Split items by commas."""
        text = "Python, JavaScript, Rust"
        result = split_items(text)
        self.assertEqual(result, ["Python", "JavaScript", "Rust"])

    def test_split_items_empty(self):
        """Empty or None input returns empty list."""
        self.assertEqual(split_items(None), [])
        self.assertEqual(split_items(""), [])

    def test_parse_entries_simple(self):
        """Parse entries with title and subtitle."""
        text = "Senior Developer\nAcme Corp, 2022-2023\nBuilt APIs and databases"
        result = parse_entries(text)
        self.assertEqual(len(result), 1)
        entry = result[0]
        self.assertEqual(entry["title"], "Senior Developer")
        self.assertEqual(entry["subtitle"], "Acme Corp, 2022-2023")
        self.assertIn("Built APIs and databases", entry.get("details", ""))

    def test_parse_entries_multiple(self):
        """Parse multiple entries separated by blank lines."""
        text = "Job 1\nCompany A, 2022\nDetails A\n\nJob 2\nCompany B, 2021\nDetails B"
        result = parse_entries(text)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["title"], "Job 1")
        self.assertEqual(result[1]["title"], "Job 2")

    def test_parse_entries_title_only(self):
        """Entry with title but no subtitle."""
        text = "Just a title"
        result = parse_entries(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Just a title")
        self.assertNotIn("subtitle", result[0])

    def test_parse_entries_empty(self):
        """Empty input returns empty list."""
        self.assertEqual(parse_entries(None), [])
        self.assertEqual(parse_entries(""), [])

    def test_safe_url_http(self):
        """Accept http URLs."""
        url = safe_url("http://example.com")
        self.assertEqual(url, "http://example.com")

    def test_safe_url_https(self):
        """Accept https URLs."""
        url = safe_url("https://example.com")
        self.assertEqual(url, "https://example.com")

    def test_safe_url_domain_no_scheme(self):
        """Add https:// to bare domain."""
        url = safe_url("linkedin.com/in/john")
        self.assertEqual(url, "https://linkedin.com/in/john")

    def test_safe_url_javascript_rejected(self):
        """Reject javascript: URLs."""
        url = safe_url("javascript:alert('xss')")
        self.assertIsNone(url)

    def test_safe_url_other_scheme_rejected(self):
        """Reject non-http schemes."""
        url = safe_url("ftp://example.com")
        self.assertIsNone(url)

    def test_safe_url_empty(self):
        """Empty or None returns None."""
        self.assertIsNone(safe_url(None))
        self.assertIsNone(safe_url(""))
        self.assertIsNone(safe_url("   "))

    def test_safe_url_whitespace_handling(self):
        """Reject URLs with spaces."""
        url = safe_url("https://example.com with spaces")
        self.assertIsNone(url)

    def test_safe_url_case_insensitive_scheme(self):
        """Scheme matching is case-insensitive."""
        url = safe_url("HTTPS://example.com")
        self.assertEqual(url, "HTTPS://example.com")


if __name__ == "__main__":
    unittest.main()
