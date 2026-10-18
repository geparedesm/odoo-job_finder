"""User profiles populated from uploaded CVs."""

import base64
from io import BytesIO

from odoo import fields, models
from odoo.exceptions import UserError

from .cv_parser import parse_cv_text


class JobProfile(models.Model):
    _name = "job.profile"
    _description = "Professional profile"

    # Odoo 19 declares table constraints as models.Constraint; _sql_constraints is no longer applied.
    _user_uniq = models.Constraint("UNIQUE (user_id)", "A profile already exists for this user.")

    user_id = fields.Many2one(
        "res.users", string="User", required=True,
        default=lambda self: self.env.user, ondelete="cascade",
    )
    portfolio_slug = fields.Char(
        string="Portfolio URL slug", related="user_id.portfolio_slug", store=True,
        index=True, readonly=True,
    )
    full_name = fields.Char(string="Full name")
    headline = fields.Char(string="Professional headline")
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
    cv_file = fields.Binary(string="CV PDF")
    cv_filename = fields.Char(string="File name")
    cv_raw_text = fields.Text(string="Extracted CV text", readonly=True)
    cv_parsed_date = fields.Datetime(string="Parsed date", readonly=True)

    portfolio_initials = fields.Char(compute="_compute_portfolio_initials")

    def _compute_portfolio_initials(self):
        for profile in self:
            name = (profile.full_name or "").split()
            profile.portfolio_initials = "".join(part[0] for part in name[:2]).upper() or "?"

    def action_open_my_profile(self):
        profile = self.search([("user_id", "=", self.env.uid)], limit=1)
        if not profile:
            profile = self.create({"user_id": self.env.uid})
        if getattr(profile, "user_id", False):
            profile.user_id._ensure_portfolio_slugs()
        # _for_xml_id: internal users cannot read action records directly.
        action = self.env["ir.actions.act_window"]._for_xml_id("job_finder.action_my_profile")
        action.update(res_id=profile.id, views=[(False, "form")])
        return action

    def action_parse_cv(self):
        try:
            import pypdf
        except ImportError as exc:
            raise UserError("Instale la librería pypdf para analizar el CV.") from exc

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
