"""Common fields of the records that make up a structured profile."""

from odoo import fields, models


class ProfileItem(models.AbstractModel):
    _name = "job_finder.profile_item"
    _description = "Profile item"
    _order = "sequence, id"

    profile_id = fields.Many2one(
        "job.profile", string="Profile", required=True, index=True, ondelete="cascade",
    )
    sequence = fields.Integer(string="Sequence", default=10)
    is_public = fields.Boolean(
        string="Show on portfolio", default=True,
        help="When unchecked, the entry stays in the complete CV but is hidden from the public portfolio.",
    )
