"""Areas a CV can focus on: Frontend, Backend, DevOps, Hospitality…"""

from odoo import fields, models


class CvArea(models.Model):
    _name = "job_finder.cv_area"
    _description = "CV area"
    _order = "sequence, id"

    profile_id = fields.Many2one(
        "job.profile", string="Profile", required=True, index=True, ondelete="cascade",
    )
    sequence = fields.Integer(string="Sequence", default=10)
    name = fields.Char(string="Area", required=True, translate=True, help="For example Backend or Hospitality.")
    headline = fields.Char(
        string="CV headline", translate=True,
        help="Headline of a CV for this area, for example Backend Developer. Defaults to the profile headline.",
    )
    summary = fields.Text(
        string="CV summary", translate=True,
        help="Professional summary of a CV for this area. Defaults to the profile summary.",
    )
