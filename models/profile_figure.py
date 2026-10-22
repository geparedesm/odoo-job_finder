"""Key figures of a profile, shown under the portfolio's introduction."""

from odoo import fields, models


class ProfileFigure(models.Model):
    _name = "job_finder.profile_figure"
    _inherit = "job_finder.profile_item"
    _description = "Profile key figure"

    value = fields.Char(string="Value", required=True, help="For example 6 yrs or 55k+.")
    label = fields.Char(string="Label", required=True, translate=True, help="For example App downloads.")
