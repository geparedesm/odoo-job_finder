"""Skill areas of a profile, each with its technologies."""

from odoo import fields, models


class SkillGroup(models.Model):
    _name = "job_finder.skill_group"
    _inherit = ["job_finder.profile_item", "job_finder.cv_area_mixin"]
    _description = "Profile skill group"

    name = fields.Char(string="Area", required=True, translate=True)
    technology_ids = fields.Many2many("job_finder.technology", string="Technologies")
