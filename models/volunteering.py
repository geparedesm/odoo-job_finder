"""Leadership, community and volunteering roles of a profile."""

from odoo import fields, models

from .portfolio_content import highlight_lines


class Volunteering(models.Model):
    _name = "job_finder.volunteering"
    _inherit = "job_finder.profile_item"
    _description = "Profile volunteering"

    title = fields.Char(string="Title", required=True, translate=True)
    organisation = fields.Char(string="Organisation")
    location = fields.Char(string="Location", translate=True)
    period = fields.Char(string="Period", translate=True, help="For example 2024 – 2026, or one period per role.")
    highlights = fields.Text(string="Highlights", translate=True, help="One achievement per line.")
    recognitions = fields.Text(string="Roles and recognition", translate=True, help="One role or award per line.")

    def _get_highlight_lines(self):
        self.ensure_one()
        return highlight_lines(self.highlights)

    def _get_recognition_lines(self):
        self.ensure_one()
        return highlight_lines(self.recognitions)
