"""Profile settings for personal job searches."""

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class JobSearchProfile(models.Model):
    _inherit = "job.profile"

    visa_status = fields.Char(string="Visa status", default="Temporary graduate (subclass 485)")
    work_rights_until = fields.Date(string="Work rights until", default="2028-02-28")
    score_threshold = fields.Integer(string="Score threshold", default=40)
    max_offer_age = fields.Integer(string="Max offer age (days)", default=7)

    @api.constrains("score_threshold", "max_offer_age")
    def _check_search_settings(self):
        for profile in self:
            if not 0 <= profile.score_threshold <= 100 or profile.max_offer_age < 1:
                raise ValidationError(self.env._("Invalid search settings."))
