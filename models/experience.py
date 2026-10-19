"""Roles of a profile: professional positions and academic research collaborations."""

from babel.dates import format_date

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.misc import babel_locale_parse


class Experience(models.Model):
    _name = "job_finder.experience"
    _inherit = "job_finder.profile_item"
    _description = "Profile experience"
    _order = "sequence, date_start desc, id"

    category = fields.Selection(
        [("work", "Professional experience"), ("research", "Academic research")],
        string="Category", required=True, default="work",
    )
    role = fields.Char(string="Role", required=True, translate=True)
    company = fields.Char(string="Company or organisation")
    location = fields.Char(string="Location", translate=True)
    employment_type = fields.Selection(
        [
            ("full_time", "Full-time"),
            ("part_time", "Part-time"),
            ("casual", "Casual"),
            ("contract", "Contract"),
            ("freelance", "Freelance"),
            ("internship", "Internship"),
            ("academic", "Academic collaboration"),
        ],
        string="Employment type",
    )
    date_start = fields.Date(string="Start")
    date_end = fields.Date(string="End")
    is_current = fields.Boolean(string="I currently work here")
    is_year_only = fields.Boolean(string="Show years only", help="For roles whose months are not known.")
    description = fields.Text(string="Description", translate=True)
    highlights = fields.Text(
        string="Highlights", translate=True,
        help="One achievement per line, shown as bullets on the portfolio and the CV.",
    )
    project_ids = fields.One2many("job_finder.project", "experience_id", string="Projects")

    @api.constrains("date_start", "date_end", "is_current")
    def _check_dates(self):
        for experience in self:
            if experience.date_start and experience.date_end and not experience.is_current \
                    and experience.date_end < experience.date_start:
                raise ValidationError(self.env._("The end of a role cannot be before its start."))

    @api.depends("role", "company")
    def _compute_display_name(self):
        for experience in self:
            experience.display_name = " · ".join(filter(None, [experience.role, experience.company]))

    @api.onchange("is_current")
    def _onchange_is_current(self):
        if self.is_current:
            self.date_end = False

    def _get_period_label(self):
        """'Dec 2021 – Jan 2025' or 'Dec 2021 – Present' in the context language."""
        self.ensure_one()
        return period_label(self.env, self.date_start, False if self.is_current else self.date_end,
                            is_current=self.is_current, is_year_only=self.is_year_only)

    def _get_highlight_lines(self):
        self.ensure_one()
        return highlight_lines(self.highlights)


def period_label(env, date_start, date_end, *, is_current=False, is_year_only=False):
    """A period such as 'Dec 2021 – Jan 2025' or '2023 – 2024', localized with the context language."""
    locale = babel_locale_parse(env.lang or "en_US")
    pattern = "y" if is_year_only else "MMM y"
    start = format_date(date_start, pattern, locale=locale) if date_start else ""
    if is_current:
        end = env._("Present")
    else:
        end = format_date(date_end, pattern, locale=locale) if date_end else ""
    if start and end and start != end:
        return f"{start} – {end}"
    return start or end


def highlight_lines(text):
    """Non-empty lines of a highlights field, without leading bullets."""
    lines = ((line.strip().lstrip("•-*").strip()) for line in (text or "").splitlines())
    return [line for line in lines if line]
