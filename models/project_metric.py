"""Key outcomes of a project, shown on its case-study page."""

from odoo import fields, models


class ProjectMetric(models.Model):
    _name = "job_finder.project_metric"
    _description = "Project key outcome"
    _order = "sequence, id"

    project_id = fields.Many2one(
        "job_finder.project", string="Project", required=True, index=True, ondelete="cascade",
    )
    sequence = fields.Integer(string="Sequence", default=10)
    value = fields.Char(string="Value", required=True, help="For example +40% or 90%.")
    label = fields.Char(string="Label", required=True, translate=True, help="For example Operations per minute.")
