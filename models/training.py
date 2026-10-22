"""Trainings, licences and credentials of a profile."""

from odoo import fields, models


class Training(models.Model):
    _name = "job_finder.training"
    _inherit = ["job_finder.profile_item", "job_finder.cv_area_mixin"]
    _description = "Profile training or credential"
    _order = "sequence, year desc, id"

    name = fields.Char(string="Name", required=True, translate=True)
    issuer = fields.Char(string="Issuer")
    year = fields.Integer(string="Year")
    status = fields.Selection(
        [("current", "Current"), ("expired", "Expired"), ("not_renewed", "Not renewed")],
        string="Status",
    )
