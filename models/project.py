"""Projects of a profile, usually delivered within a role."""

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .portfolio_content import safe_url


class Project(models.Model):
    _name = "job_finder.project"
    _inherit = ["job_finder.profile_item", "job_finder.cv_area_mixin"]
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
    # Case study: featured projects get their own portfolio page.
    area = fields.Char(string="Area", translate=True, help="Shown above the project name, for example Access control.")
    cover_image = fields.Image(string="Cover", max_width=1920, max_height=1920)
    platforms = fields.Char(string="Platforms", translate=True, help="For example Android · iOS · Web.")
    highlights = fields.Text(
        string="What I built", translate=True,
        help="One item per line. 'Title: description' shows the title in bold.",
    )
    metric_ids = fields.One2many("job_finder.project_metric", "project_id", string="Key outcomes")
    step_ids = fields.One2many("job_finder.project_step", "project_id", string="Architecture")

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

    def _get_portfolio_path(self):
        """The case-study page, for example /portfolio/project/zkteco-platform-12."""
        self.ensure_one()
        return f"/portfolio/project/{self.env['ir.http']._slug(self)}"
