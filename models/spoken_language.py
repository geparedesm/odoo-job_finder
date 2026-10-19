"""Languages a profile speaks, with their level."""

from odoo import fields, models


class SpokenLanguage(models.Model):
    _name = "job_finder.spoken_language"
    _inherit = "job_finder.profile_item"
    _description = "Profile spoken language"

    name = fields.Char(string="Language", required=True, translate=True)
    level = fields.Selection(
        [
            ("native", "Native"),
            ("c2", "C2 · Proficient"),
            ("c1", "C1 · Advanced"),
            ("b2", "B2 · Upper intermediate"),
            ("b1", "B1 · Intermediate"),
            ("a2", "A2 · Elementary"),
            ("a1", "A1 · Beginner"),
        ],
        string="Level",
    )
