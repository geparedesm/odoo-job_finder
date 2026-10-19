"""User profiles populated from uploaded CVs."""

import base64
import re
from io import BytesIO

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError

from . import cv_structure
from .cv_parser import parse_cv_text
from .portfolio_content import (
    capitalize_first, en_dash_ranges, first_sentence, headline_parts, highlight_lines, paragraphs, safe_url,
    split_organisation,
)


LINK_ICONS = {"linkedin": "fa-linkedin", "github": "fa-github", "website": "fa-globe"}


class JobProfile(models.Model):
    _name = "job.profile"
    _inherit = ["website.seo.metadata"]
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
    is_phone_public = fields.Boolean(
        string="Show phone on portfolio", help="The phone always appears in the complete CV.")

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
            project_sequence = iter(range(1, 10000))  # one order across roles, as listed in the CV
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
                        "sequence": next(project_sequence),
                        "name": project["name"],
                        "subtitle": project["subtitle"],
                        "description": project["description"],
                        "category": project["category"],
                        "is_featured": project["category"] == "work",
                        "technology_ids": [Command.set(Technology._find_or_create(project["technologies"]).ids)],
                    }) for project in role["projects"]],
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

    def _default_website_meta(self):
        """Portfolio sharing defaults: name and headline as title, the summary as description, the photo as image."""
        meta = super()._default_website_meta()
        title = " | ".join(filter(None, [self.full_name, ", ".join(headline_parts(self.headline))]))
        if title:
            meta["default_opengraph"]["og:title"] = meta["default_twitter"]["twitter:title"] = title
        description = " ".join(paragraphs(self.summary))[:300]
        if description:
            meta["default_opengraph"]["og:description"] = meta["default_twitter"]["twitter:description"] = description
            meta["default_meta_description"] = description
        if self.photo and self.is_published_as_portfolio:
            meta["default_opengraph"]["og:image"] = meta["default_twitter"]["twitter:image"] = "/portfolio/photo"
        return meta

    def action_open_my_profile(self):
        profile = self.search([("user_id", "=", self.env.uid)], limit=1)
        if not profile:
            profile = self.create({"user_id": self.env.uid})
        # _for_xml_id: internal users cannot read action records directly.
        action = self.env["ir.actions.act_window"]._for_xml_id("job_finder.action_my_profile")
        action.update(res_id=profile.id, views=[(False, "form")])
        return action

    def _get_portfolio_values(self):
        """The public part of the profile, ready for the portfolio page: only entries shown on the portfolio,
        texts in the context language, and no phone unless the person chose to show it."""
        self.ensure_one()

        def selection_label(record, field):
            return dict(record._fields[field]._description_selection(self.env)).get(record[field], "")

        def first_line(text):
            return first_sentence(next(iter(highlight_lines(text)), ""))

        def link(value):
            url = safe_url(value)
            return {"href": url, "label": re.sub(r"^https?://(www\.)?", "", url).rstrip("/")} if url else None

        roles = self.experience_ids.filtered("is_public")
        projects = self.project_ids.filtered("is_public")
        featured = projects.filtered(lambda p: p.is_featured)
        work_roles = roles.filtered(lambda r: r.category == "work")
        research_roles = roles.filtered(lambda r: r.category == "research")
        featured_by_role = {role.id: len(featured.filtered(lambda p, r=role: p.experience_id == r)) for role in work_roles}
        links = {name: link(self[name]) for name in ("linkedin", "github", "website")}
        return {
            "name": self.full_name or "",
            "headline_parts": headline_parts(self.headline),
            "location": self.location or "",
            "summary_paragraphs": paragraphs(self.summary),
            "email": self.email or "",
            "phone": self.phone if self.is_phone_public else "",
            "has_photo": bool(self.photo),
            "links": [dict(kind=name, icon=LINK_ICONS[name], **value) for name, value in links.items() if value],
            "featured_projects": [{
                "name": project.name,
                "subtitle": capitalize_first(project.subtitle),
                "source": " / ".join(filter(None, [project.experience_id.company,
                                                   project.experience_id._get_period_label() if project.experience_id else ""])),
                "description": first_line(project.description),
                "technologies": ", ".join(project.technology_ids.mapped("name")),
                "url": project._get_url(),
            } for project in featured],
            "roles": [{
                "period": role._get_period_label(),
                "title": " / ".join(filter(None, [role.role, role.company])),
                "detail": (self.env._("%(count)s projects in Selected work", count=featured_by_role[role.id])
                           if featured_by_role[role.id] > 1 else
                           self.env._("1 project in Selected work") if featured_by_role[role.id] == 1 else
                           first_line(role.highlights) or first_line(role.description)),
                "location": role.location or "",
                "type": selection_label(role, "employment_type") if role.employment_type else "",
            } for role in work_roles],
            "research_groups": [{
                "organisation": split_organisation(role.company)[0] or role.role,
                "role": role.role if role.company else "",
                "meta": " / ".join(filter(None, [split_organisation(role.company)[1], role.location,
                                                 role._get_period_label()])),
                "items": [{"name": project.name, "technologies": ", ".join(project.technology_ids.mapped("name"))}
                          for project in role.project_ids.filtered("is_public")],
            } for role in research_roles],
            "skills": [{"name": group.name, "items": " / ".join(group.technology_ids.mapped("name"))}
                       for group in self.skill_group_ids.filtered("is_public")],
            "education": [{
                "qualification": entry.qualification,
                "meta": " / ".join(filter(None, [
                    entry.code,
                    ", ".join(filter(None, [entry.institution, entry.location])),
                    entry._get_period_label() if entry.year_start else "",
                    " ".join(filter(None, [selection_label(entry, "status") if entry.status else "",
                                           str(entry.year_end) if entry.year_end and not entry.year_start else ""])),
                ])),
            } for entry in self.education_ids.filtered("is_public")],
            "trainings": [{
                "name": training.name,
                "meta": " / ".join(filter(None, [training.issuer,
                                                 selection_label(training, "status") if training.status else ""])),
                "year": str(training.year) if training.year else "",
            } for training in self.training_ids.filtered("is_public")],
            "languages": [{
                "name": language.name,
                "level": (selection_label(language, "level").split(" · ")[0] if language.level else ""),
            } for language in self.spoken_language_ids.filtered("is_public")],
            "volunteering": [{
                "title": entry.title,
                "meta": " / ".join(filter(None, [entry.organisation, entry.location, en_dash_ranges(entry.period)])),
                "highlight": first_line(entry.highlights),
                "recognitions": entry._get_recognition_lines(),
            } for entry in self.volunteering_ids.filtered("is_public")],
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
