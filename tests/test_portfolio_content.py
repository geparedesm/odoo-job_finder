"""Text helpers of the public portfolio (standard library only)."""

import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "portfolio_content", Path(__file__).parent.parent / "models" / "portfolio_content.py")
portfolio_content = importlib.util.module_from_spec(spec)
spec.loader.exec_module(portfolio_content)


class PortfolioContentTestCase(unittest.TestCase):
    def test_safe_url(self):
        safe_url = portfolio_content.safe_url
        self.assertEqual(safe_url("https://example.com"), "https://example.com")
        self.assertEqual(safe_url("HTTP://example.com"), "HTTP://example.com")
        self.assertEqual(safe_url("linkedin.com/in/john"), "https://linkedin.com/in/john")
        for unsafe in ("javascript:alert('xss')", "ftp://example.com", "https://example.com with spaces",
                       "localhost", None, "", "   "):
            self.assertIsNone(safe_url(unsafe), unsafe)

    def test_capitalize_first(self):
        self.assertEqual(portfolio_content.capitalize_first("music social application"), "Music social application")
        self.assertEqual(portfolio_content.capitalize_first("Ecuadorian Navy"), "Ecuadorian Navy")
        self.assertEqual(portfolio_content.capitalize_first(None), "")

    def test_headline_parts(self):
        self.assertEqual(portfolio_content.headline_parts("SOFTWARE DEVELOPMENT | ICT | MECHATRONICS"),
                         ["Software development", "ICT", "Mechatronics"])
        self.assertEqual(portfolio_content.headline_parts("Data Engineer"), ["Data Engineer"])
        self.assertEqual(portfolio_content.headline_parts(" | "), [])
        self.assertEqual(portfolio_content.headline_parts(None), [])

    def test_paragraphs(self):
        text = "First line\nwrapped by the PDF.\n\nSecond paragraph."
        self.assertEqual(portfolio_content.paragraphs(text), ["First line wrapped by the PDF.", "Second paragraph."])
        self.assertEqual(portfolio_content.paragraphs("  \n  "), [])
        self.assertEqual(portfolio_content.paragraphs(None), [])

    def test_first_sentence(self):
        first = portfolio_content.first_sentence
        self.assertEqual(first("Built pipelines for Sophos logs. Developed scripts."), "Built pipelines for Sophos logs.")
        self.assertEqual(first("Upgraded the stack from 8.4.2 to 8.14.2."), "Upgraded the stack from 8.4.2 to 8.14.2.")
        self.assertEqual(first("No final period"), "No final period")
        self.assertEqual(first(None), "")

    def test_en_dash_ranges(self):
        self.assertEqual(portfolio_content.en_dash_ranges("Ambassador: 2025 - 2026"), "Ambassador: 2025 – 2026")
        self.assertEqual(portfolio_content.en_dash_ranges("Redux-Saga - React"), "Redux-Saga - React")

    def test_split_organisation(self):
        self.assertEqual(portfolio_content.split_organisation("Systems Group, Universidad Técnica del Norte"),
                         ("Universidad Técnica del Norte", "Systems Group"))
        self.assertEqual(portfolio_content.split_organisation("NIT"), ("NIT", ""))

    def test_highlight_lines(self):
        self.assertEqual(portfolio_content.highlight_lines("• One\n\n- Two\n  Three  "), ["One", "Two", "Three"])
        self.assertEqual(portfolio_content.highlight_lines(False), [])


if __name__ == "__main__":
    unittest.main()
