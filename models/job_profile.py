"""User profiles populated from uploaded CVs."""

import base64
from io import BytesIO

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .cv_parser import parse_cv_text
from .portfolio_content import parse_entries, parse_expertise, safe_url, split_items


class JobProfile(models.Model):
    _name = "job.profile"
    _description = "Professional profile"

    # Odoo 19 declares table constraints as models.Constraint; _sql_constraints is no longer applied.
    _user_uniq = models.Constraint("UNIQUE (user_id)", "A profile already exists for this user.")
    # The Python constraint gives the readable error; this database constraint keeps concurrent publications atomic.
    # It is deferred to commit, so unpublishing one profile and publishing another in one transaction is allowed.
    _single_portfolio = models.Constraint(
        "EXCLUDE USING btree (is_published_as_portfolio WITH =) WHERE (is_published_as_portfolio) DEFERRABLE INITIALLY DEFERRED",
        "Only one profile can be published as the portfolio.",
    )

    user_id = fields.Many2one(
        "res.users", string="User", required=True,
        default=lambda self: self.env.user, ondelete="cascade",
    )
    full_name = fields.Char(string="Full name")
    headline = fields.Char(string="Headline")
    email = fields.Char(string="Email")
    phone = fields.Char(string="Phone")
    location = fields.Char(string="Location")
    linkedin = fields.Char(string="LinkedIn")
    website = fields.Char(string="Website")
    github = fields.Char(string="GitHub")
    summary = fields.Text(string="Summary")
    skills = fields.Text(string="Skills")
    experience = fields.Text(string="Experience")
    education = fields.Text(string="Education")
    languages = fields.Text(string="Languages")
    volunteering = fields.Text(
        string="Volunteering", help="Leadership and volunteering experience from the CV.",
    )
    projects = fields.Text(
        string="Projects", help="Academic research and projects from the CV.",
    )
    trainings = fields.Text(
        string="Trainings", help="Training and credentials from the CV.",
    )
    cv_file = fields.Binary(string="CV (PDF)")
    cv_filename = fields.Char(string="File name")
    cv_raw_text = fields.Text(string="Extracted CV text", readonly=True)
    cv_parsed_date = fields.Datetime(string="Analysis date", readonly=True)
    is_published_as_portfolio = fields.Boolean(
        string="Publish as portfolio", copy=False, groups="base.group_system",
    )

    @api.constrains("is_published_as_portfolio")
    def _check_single_portfolio(self):
        """Only one profile can be published as the portfolio."""
        for profile in self:
            if not profile.is_published_as_portfolio:
                continue
            # Minimal sudo: only to count other published profiles when record rules hide them.
            count = self.env["job.profile"].sudo().search_count(
                [("is_published_as_portfolio", "=", True), ("id", "!=", profile.id)]
            )
            if count > 0:
                raise ValidationError(self.env._("Only one profile can be published as the portfolio."))

    def action_open_my_profile(self):
        profile = self.search([("user_id", "=", self.env.uid)], limit=1)
        if not profile:
            profile = self.create({"user_id": self.env.uid})
        # _for_xml_id: internal users cannot read action records directly.
        action = self.env["ir.actions.act_window"]._for_xml_id("job_finder.action_my_profile")
        action.update(res_id=profile.id, views=[(False, "form")])
        return action

    def _get_portfolio_values(self):
        """Return a whitelisted dict of public fields with parsed content for portfolio display."""
        self.ensure_one()
        return {
            "name": self.full_name or "",
            "headline": self.headline or "",
            "location": self.location or "",
            "summary": self.summary or "",
            "skills": split_items(self.skills),
            "expertise": parse_expertise(self.skills),
            "projects": parse_entries(self.projects),
            "experience": parse_entries(self.experience),
            "education": parse_entries(self.education),
            "trainings": split_items(self.trainings),
            "volunteering": split_items(self.volunteering),
            "languages": split_items(self.languages),
            "email": self.email or "",
            "linkedin": safe_url(self.linkedin),
            "github": safe_url(self.github),
            "website": safe_url(self.website),
        }

    def action_parse_cv(self):
        try:
            import pypdf
        except ImportError as exc:
            raise UserError(self.env._("Install the pypdf library to analyze the CV.")) from exc

        profile_fields = (
            "full_name", "headline", "email", "phone", "location", "linkedin", "website", "github",
            "summary", "skills", "experience", "education",
            "languages", "volunteering", "projects", "trainings",
        )
        for profile in self:
            if not profile.cv_file:
                continue
            page_texts = []
            try:
                reader = pypdf.PdfReader(BytesIO(base64.b64decode(profile.cv_file)))
                for page in reader.pages:
                    try:
                        page_texts.append(page.extract_text() or "")
                    except Exception:
                        # A damaged page must not discard other readable pages.
                        continue
            except Exception:
                # Invalid or unreadable PDFs still produce an empty debug cache.
                pass
            text = "\n".join(page_texts)
            parsed = parse_cv_text(text)
            values = {
                name: parsed[name] for name in profile_fields if parsed.get(name)
            }
            values.update(
                cv_raw_text=text, cv_parsed_date=fields.Datetime.now(),
            )
            profile.write(values)
