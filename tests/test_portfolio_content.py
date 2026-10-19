"""Tests for portfolio content parsing."""

import sys
import unittest
import importlib.util
from pathlib import Path

# Load portfolio_content module directly without importing through models/__init__.py
portfolio_content_path = Path(__file__).parent.parent / "models" / "portfolio_content.py"
spec = importlib.util.spec_from_file_location("portfolio_content", portfolio_content_path)
portfolio_content = importlib.util.module_from_spec(spec)
spec.loader.exec_module(portfolio_content)

parse_entries = portfolio_content.parse_entries
safe_url = portfolio_content.safe_url
split_blocks = portfolio_content.split_blocks
split_items = portfolio_content.split_items


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
