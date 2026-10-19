"""User profiles populated from uploaded CVs."""

import base64
from io import BytesIO

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError

from . import cv_structure
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
    headline = fields.Char(string="Headline", translate=True)
    photo = fields.Image(string="Photo", max_width=1024, max_height=1024)
    email = fields.Char(string="Email")
    phone = fields.Char(string="Phone")
    location = fields.Char(string="Location", translate=True)
    linkedin = fields.Char(string="LinkedIn")
    website = fields.Char(string="Website")
    github = fields.Char(string="GitHub")
    summary = fields.Text(string="Summary", translate=True)

    experience_ids = fields.One2many("job_finder.experience", "profile_id", string="Experience")
    project_ids = fields.One2many("job_finder.project", "profile_id", string="Projects")
    skill_group_ids = fields.One2many("job_finder.skill_group", "profile_id", string="Skills")
    education_ids = fields.One2many("job_finder.education", "profile_id", string="Education")
    training_ids = fields.One2many("job_finder.training", "profile_id", string="Trainings")
    volunteering_ids = fields.One2many("job_finder.volunteering", "profile_id", string="Volunteering")
    spoken_language_ids = fields.One2many("job_finder.spoken_language", "profile_id", string="Languages")
    completeness = fields.Integer(string="Completeness", compute="_compute_completeness")
    completeness_hints = fields.Text(string="Missing information", compute="_compute_completeness")

    # The CV sections as extracted text. The structured records above are built from them; they are kept read-only
    # as the source of the last import.
    skills = fields.Text(string="Skills (imported text)", readonly=True)
    experience = fields.Text(string="Experience (imported text)", readonly=True)
    education = fields.Text(string="Education (imported text)", readonly=True)
    languages = fields.Text(string="Languages (imported text)", readonly=True)
    volunteering = fields.Text(string="Volunteering (imported text)", readonly=True)
    projects = fields.Text(string="Projects (imported text)", readonly=True)
    trainings = fields.Text(string="Trainings (imported text)", readonly=True)
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

    @api.depends(
        "full_name", "headline", "summary", "email", "photo", "experience_ids.date_start",
        "experience_ids.is_current", "experience_ids.date_end", "skill_group_ids", "spoken_language_ids.level",
        "education_ids",
    )
    def _compute_completeness(self):
        for profile in self:
            checks = [
                (bool(profile.full_name), self.env._("Add your full name.")),
                (bool(profile.headline), self.env._("Add a headline.")),
                (bool(profile.summary), self.env._("Write a summary.")),
                (bool(profile.email), self.env._("Add an email address.")),
                (bool(profile.photo), self.env._("Add a photo.")),
                (bool(profile.experience_ids), self.env._("Add at least one role.")),
                (all(e.date_start and (e.date_end or e.is_current) for e in profile.experience_ids),
                 self.env._("Complete the dates of every role.")),
                (bool(profile.skill_group_ids), self.env._("Add your skills.")),
                (bool(profile.spoken_language_ids) and all(lang.level for lang in profile.spoken_language_ids),
                 self.env._("Add your languages with their level.")),
                (bool(profile.education_ids), self.env._("Add your education.")),
            ]
            profile.completeness = round(100 * sum(ok for ok, _hint in checks) / len(checks))
            profile.completeness_hints = "\n".join(hint for ok, hint in checks if not ok)

    def _set_structured_sections(self, sections):
        """Replace the profile's records with those parsed from CV section texts.

        `sections` maps the text fields (experience, projects, skills, education, trainings, volunteering,
        languages) to their text. A section that is missing or empty keeps its existing records.
        """
        self.ensure_one()
        Technology = self.env["job_finder.technology"]
        commands = {}
        roles = []
        if sections.get("experience"):
            roles += cv_structure.parse_roles(sections["experience"], "work")
        if sections.get("projects"):
            roles += cv_structure.parse_roles(sections["projects"], "research")
        if roles:
            categories = {role["category"] for role in roles}
            self.experience_ids.filtered(lambda e: e.category in categories).unlink()
            self.project_ids.filtered(lambda p: p.category in categories).unlink()
            for sequence, role in enumerate(roles, start=1):
                self.env["job_finder.experience"].create({
                    "profile_id": self.id,
                    "sequence": sequence,
                    **{key: role[key] for key in ("role", "company", "location", "date_start", "date_end",
                                                  "is_current", "is_year_only", "employment_type", "category",
                                                  "description")},
                    "highlights": "\n".join(role["highlights"]),
                    "project_ids": [Command.create({
                        "profile_id": self.id,
                        "sequence": index,
                        "name": project["name"],
                        "subtitle": project["subtitle"],
                        "description": project["description"],
                        "category": project["category"],
                        "is_featured": project["category"] == "work",
                        "technology_ids": [Command.set(Technology._find_or_create(project["technologies"]).ids)],
                    }) for index, project in enumerate(role["projects"], start=1)],
                })
        if sections.get("skills"):
            commands["skill_group_ids"] = [Command.clear()] + [Command.create({
                "sequence": sequence, "name": group["name"],
                "technology_ids": [Command.set(Technology._find_or_create(group["technologies"]).ids)],
            }) for sequence, group in enumerate(cv_structure.parse_skill_groups(sections["skills"]), start=1)]
        if sections.get("education"):
            commands["education_ids"] = [Command.clear()] + [
                Command.create({"sequence": sequence, **entry})
                for sequence, entry in enumerate(cv_structure.parse_education(sections["education"]), start=1)]
        if sections.get("trainings"):
            commands["training_ids"] = [Command.clear()] + [
                Command.create({"sequence": sequence, **entry})
                for sequence, entry in enumerate(cv_structure.parse_trainings(sections["trainings"]), start=1)]
        if sections.get("volunteering"):
            commands["volunteering_ids"] = [Command.clear()] + [Command.create({
                "sequence": sequence,
                **{key: entry[key] for key in ("title", "organisation", "location", "period")},
                "highlights": "\n".join(entry["highlights"]),
                "recognitions": "\n".join(entry["recognitions"]),
            }) for sequence, entry in enumerate(cv_structure.parse_volunteering(sections["volunteering"]), start=1)]
        if sections.get("languages"):
            commands["spoken_language_ids"] = [Command.clear()] + [
                Command.create({"sequence": sequence, **entry})
                for sequence, entry in enumerate(cv_structure.parse_spoken_languages(sections["languages"]), start=1)]
        if commands:
            self.write(commands)

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
            profile._set_structured_sections(parsed)
