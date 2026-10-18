"""Static checks for the public portfolio template and responsive stylesheet."""

from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parent.parent


class TestPortfolioTemplate(unittest.TestCase):
    def test_template_is_valid_and_contains_profile_sections(self):
        template = ROOT / "views" / "portfolio_templates.xml"
        ET.parse(template)
        source = template.read_text(encoding="utf-8")
        for section in ("summary", "skills", "experience", "education", "volunteering", "projects", "trainings", "languages"):
            with self.subTest(section=section):
                self.assertIn(section, source)
        self.assertIn("profile.portfolio_initials", source)
        self.assertIn("/portfolio/<string:slug>", (ROOT / "controllers" / "portfolio.py").read_text())

    def test_stylesheet_has_mobile_first_breakpoints_and_accessible_focus(self):
        css = (ROOT / "static" / "src" / "css" / "portfolio.css").read_text(encoding="utf-8")
        self.assertIn("#070b12", css.lower())
        self.assertIn("@media (min-width: 700px)", css)
        self.assertIn("@media (min-width: 1100px)", css)
        self.assertIn("prefers-reduced-motion", css)


if __name__ == "__main__":
    unittest.main()
