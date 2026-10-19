"""Qualifications of a profile."""

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class Education(models.Model):
    _name = "job_finder.education"
    _inherit = "job_finder.profile_item"
    _description = "Profile education"
    _order = "sequence, year_end desc, id"

    qualification = fields.Char(string="Qualification", required=True, translate=True)
    code = fields.Char(string="Code", help="Course code, for example ICT60220.")
    institution = fields.Char(string="Institution")
    location = fields.Char(string="Location", translate=True)
    year_start = fields.Integer(string="Start year")
    year_end = fields.Integer(string="End year")
    status = fields.Selection(
        [("in_progress", "In progress"), ("completed", "Completed"), ("graduated", "Graduated")],
        string="Status",
    )

    @api.constrains("year_start", "year_end")
    def _check_years(self):
        for education in self:
            if education.year_start and education.year_end and education.year_end < education.year_start:
                raise ValidationError(self.env._("The end year cannot be before the start year."))

    @api.depends("qualification", "institution")
    def _compute_display_name(self):
        for education in self:
            education.display_name = " · ".join(filter(None, [education.qualification, education.institution]))

    def _get_period_label(self):
        self.ensure_one()
        years = [str(year) for year in (self.year_start, self.year_end) if year]
        return " – ".join(dict.fromkeys(years))
