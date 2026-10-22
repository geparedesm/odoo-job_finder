"""The CV-area tags of the entries of a profile (roles, projects, skills, trainings, volunteering)."""

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class CvAreaMixin(models.AbstractModel):
    _name = "job_finder.cv_area_mixin"
    _description = "Entry tagged with CV areas"

    cv_area_ids = fields.Many2many(
        "job_finder.cv_area", string="CV areas", domain="[('profile_id', '=', profile_id)]",
        help="Entries without areas appear in every CV; tagged entries only in the CVs of their areas.",
    )

    @api.constrains("cv_area_ids", "profile_id")
    def _check_cv_areas_profile(self):
        for record in self:
            if record.cv_area_ids.profile_id - record.profile_id:
                raise ValidationError(self.env._("An entry can only use the CV areas of its own profile."))

    def _filter_for_cv(self, areas):
        """The entries of a CV for these areas: untagged entries and those tagged with one of them."""
        if not areas:
            return self
        return self.filtered(lambda record: not record.cv_area_ids or record.cv_area_ids & areas)
