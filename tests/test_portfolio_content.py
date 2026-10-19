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
split_lines = portfolio_content.split_lines
parse_hosts = portfolio_content.parse_hosts
normalize_host = portfolio_content.normalize_host


class PortfolioContentTestCase(unittest.TestCase):
    """Test portfolio content splitting and parsing."""

    def test_split_blocks_simple(self):
        """Split text by blank lines into title and remaining lines."""
        text = "First block\nline a\n\nSecond block\n\n\nThird block\n- line b\n- line c"
        self.assertEqual(split_blocks(text), [
            {"title": "First block", "lines": ["line a"]},
            {"title": "Second block", "lines": []},
            {"title": "Third block", "lines": ["line b", "line c"]},
        ])

    def test_split_blocks_empty(self):
        """Empty or None input returns empty list."""
        self.assertEqual(split_blocks(None), [])
        self.assertEqual(split_blocks(""), [])
        self.assertEqual(split_blocks("   \n  \n  "), [])

    def test_split_blocks_whitespace(self):
        """Whitespace handling."""
        text = "  First  \n\n\n  Second  \n\n"
        self.assertEqual(split_blocks(text), [
            {"title": "First", "lines": []}, {"title": "Second", "lines": []},
        ])

    def test_split_lines(self):
        """Non-empty stripped lines without leading bullets."""
        text = "  • Python \n\n- Full-stack web\n* C/C++\n   \nPlain line"
        self.assertEqual(split_lines(text), ["Python", "Full-stack web", "C/C++", "Plain line"])
        self.assertEqual(split_lines(None), [])
        self.assertEqual(split_lines("  \n - \n"), [])

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

    def test_split_items_asterisks(self):
        """Split items by asterisk bullets."""
        text = "* Python\n* JavaScript\n* Rust"
        self.assertEqual(split_items(text), ["Python", "JavaScript", "Rust"])

    def test_split_items_keeps_inner_dashes(self):
        """Hyphens inside an item are not bullets."""
        text = "- Full-stack development\n- Odoo e-commerce"
        self.assertEqual(split_items(text), ["Full-stack development", "Odoo e-commerce"])
        self.assertEqual(split_items("Spanish (native); English (B2)"), ["Spanish (native)", "English (B2)"])

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

    def test_parse_hosts(self):
        """Comma-separated hosts become a lowercase set without whitespace."""
        self.assertEqual(
            parse_hosts(" GP-Developer.com, www.gp-developer.com ,,"),
            {"gp-developer.com", "www.gp-developer.com"},
        )
        self.assertEqual(parse_hosts(None), set())
        self.assertEqual(parse_hosts(" , "), set())

    def test_normalize_host(self):
        """Hosts are lowercased and lose their port."""
        self.assertEqual(normalize_host("GP-Developer.com:8069"), "gp-developer.com")
        self.assertEqual(normalize_host("www.gp-developer.com"), "www.gp-developer.com")
        self.assertEqual(normalize_host("[::1]:8069"), "[::1]")
        self.assertEqual(normalize_host(None), "")


if __name__ == "__main__":
    unittest.main()
