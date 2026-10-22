"""Architecture steps of a project, drawn as a flow on its case-study page."""

from odoo import fields, models


class ProjectStep(models.Model):
    _name = "job_finder.project_step"
    _description = "Project architecture step"
    _order = "sequence, id"

    project_id = fields.Many2one(
        "job_finder.project", string="Project", required=True, index=True, ondelete="cascade",
    )
    sequence = fields.Integer(string="Sequence", default=10)
    name = fields.Char(string="Component", required=True, translate=True, help="For example Microservices.")
    detail = fields.Char(string="Detail", translate=True, help="For example REST API · commands · sync.")
    is_highlighted = fields.Boolean(string="Highlighted", help="Shown with the accent color, for the part you built.")
