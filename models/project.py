"""Projects of a profile, usually delivered within a role."""

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .portfolio_content import safe_url


class Project(models.Model):
    _name = "job_finder.project"
    _inherit = "job_finder.profile_item"
    _description = "Profile project"

    name = fields.Char(string="Name", required=True, translate=True)
    experience_id = fields.Many2one(
        "job_finder.experience", string="Role", index=True, ondelete="set null",
        domain="[('profile_id', '=', profile_id)]",
    )
    category = fields.Selection(
        [("work", "Professional work"), ("research", "Academic research"), ("personal", "Personal project")],
        string="Category", compute="_compute_category", store=True, readonly=False, required=True,
        default="personal",
    )
    subtitle = fields.Char(string="Subtitle", translate=True, help="Client or a short description, for example Ecuadorian Navy.")
    description = fields.Text(string="Description", translate=True)
    technology_ids = fields.Many2many("job_finder.technology", string="Technologies")
    url = fields.Char(string="Link")
    is_featured = fields.Boolean(
        string="Featured", help="Featured projects are listed in the portfolio's Selected work.",
    )

    @api.depends("experience_id.category")
    def _compute_category(self):
        for project in self:
            if project.experience_id:
                project.category = project.experience_id.category

    @api.constrains("experience_id", "profile_id")
    def _check_experience_profile(self):
        for project in self:
            if project.experience_id and project.experience_id.profile_id != project.profile_id:
                raise ValidationError(self.env._("A project can only belong to a role of the same profile."))

    def _get_url(self):
        self.ensure_one()
        return safe_url(self.url)
