"""User profiles populated from uploaded CVs."""

import base64
import re
from io import BytesIO

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError

from . import cv_structure
from .cv_parser import page_text, parse_cv_text
from .portfolio_content import (
    capitalize_first, en_dash_ranges, first_sentence, headline_parts, highlight_lines, paragraphs, safe_url,
    split_organisation, split_qualification, titled_items,
)


LINK_ICONS = {"linkedin": "fa-linkedin", "github": "fa-github", "website": "fa-globe"}
# Icon of a skill area on the portfolio, from words of its name; the first match wins.
SKILL_ICONS = (
    (("language", "programming"), "fa-code"),
    (("application", "framework", "web", "mobile"), "fa-window-maximize"),
    (("data", "infra", "cloud", "devops"), "fa-database"),
    (("engineering", "hardware", "electronic", "mechatron"), "fa-microchip"),
    (("ict", "network", "analysis", "security"), "fa-sitemap"),
)
# Width of a language's level bar on the portfolio, in percent.
LANGUAGE_LEVEL_PERCENT = {"native": 100, "c2": 95, "c1": 85, "b2": 70, "b1": 55, "a2": 35, "a1": 20}


class JobProfile(models.Model):
    _name = "job.profile"
    _inherit = ["website.seo.metadata"]
    _description = "Professional profile"
    _rec_name = "full_name"

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
    tagline = fields.Char(
        string="Tagline", translate=True,
        help="One sentence under your name on the portfolio. Defaults to the first sentence of your summary.")
    availability_note = fields.Char(
        string="Availability", translate=True,
        help="Shown at the top of the portfolio, for example Open to software & ICT roles.")
    secondary_experience_title = fields.Char(
        string="Secondary experience title", translate=True,
        help="Title of the collapsible group of roles shown as secondary. Defaults to Other experience.")
    figure_ids = fields.One2many("job_finder.profile_figure", "profile_id", string="Key figures")
    # Headlines of the portfolio sections; each defaults to the section's name.
    work_heading = fields.Char(string="Selected work headline", translate=True)
    experience_heading = fields.Char(string="Experience headline", translate=True)
    skills_heading = fields.Char(string="Skills headline", translate=True)
    about_heading = fields.Char(string="Background headline", translate=True)
    contact_heading = fields.Char(string="Contact headline", translate=True)

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
                    # Roles without projects (production, hospitality…) go to the portfolio's secondary group.
                    "is_secondary": role["category"] == "work" and not role["projects"],
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

        def skill_icon(name):
            words = (name or "").casefold()
            return next((icon for keys, icon in SKILL_ICONS if any(key in words for key in keys)), "fa-cube")

        def link(value):
            url = safe_url(value)
            return {"href": url, "label": re.sub(r"^https?://(www\.)?", "", url).rstrip("/")} if url else None

        roles = self.experience_ids.filtered("is_public")
        projects = self.project_ids.filtered("is_public")
        featured = projects.filtered("is_featured")
        work_roles = roles.filtered(lambda r: r.category == "work")
        main_roles = work_roles.filtered(lambda r: not r.is_secondary)
        secondary_roles = work_roles - main_roles
        research_roles = roles.filtered(lambda r: r.category == "research")
        education = self.education_ids.filtered("is_public")
        links = {name: link(self[name]) for name in ("linkedin", "github", "website")}
        return {
            "name": self.full_name or "",
            "headline_parts": headline_parts(self.headline),
            "location": self.location or "",
            "availability": self.availability_note or "",
            "tagline": self.tagline or first_sentence(" ".join(paragraphs(self.summary)[:1])),
            "headings": {
                "work": self.work_heading or self.env._("Selected work"),
                "experience": self.experience_heading or self.env._("Experience"),
                "skills": self.skills_heading or self.env._("Skills"),
                "about": self.about_heading or self.env._("Background"),
                "contact": self.contact_heading or self.env._("Let's work together."),
            },
            "summary_paragraphs": paragraphs(self.summary),
            "email": self.email or "",
            "phone": self.phone if self.is_phone_public else "",
            "has_photo": bool(self.photo),
            "links": [dict(kind=name, icon=LINK_ICONS[name], **value) for name, value in links.items() if value],
            "figures": [{"value": figure.value, "label": figure.label}
                        for figure in self.figure_ids.filtered("is_public")],
            "latest_qualification": " · ".join(filter(None, [
                split_qualification(education[:1].qualification)[0],
                str(education[:1].year_end or "") if education else "",
            ])),
            "featured_projects": [{
                "name": project.name,
                "subtitle": capitalize_first(project.subtitle),
                "source": " / ".join(filter(None, [project.experience_id.company,
                                                   project.experience_id._get_period_label() if project.experience_id else ""])),
                "description": first_line(project.description),
                "technologies": ", ".join(project.technology_ids.mapped("name")),
                "technology_names": project.technology_ids.mapped("name"),
                "url": project._get_url(),
                "area": project.area or "",
                "index": f"{index:02d}",
                "metrics": [{"value": metric.value, "label": metric.label} for metric in project.metric_ids[:3]],
                "cover_url": f"/portfolio/project/{project.id}/cover" if project.cover_image else None,
                "page_url": project._get_portfolio_path(),
            } for index, project in enumerate(featured, start=1)],
            "roles": [{
                "period": role._get_period_label(),
                "title": role.role,
                "company": role.company or "",
                "location": role.location or "",
                "type": selection_label(role, "employment_type") if role.employment_type else "",
                "highlight": first_line(role.highlights) or first_line(role.description),
                "projects": [{"name": project.name, "url": project._get_portfolio_path() if project.is_featured else None}
                             for project in role.project_ids.filtered("is_public")],
            } for role in main_roles],
            "secondary_title": self.secondary_experience_title or self.env._("Other experience"),
            "secondary_period": " – ".join(dict.fromkeys(filter(None, [
                str(min((d.year for d in secondary_roles.mapped("date_start") if d), default="")),
                self.env._("Present") if any(secondary_roles.mapped("is_current")) else
                str(max((d.year for d in secondary_roles.mapped("date_end") if d), default="")),
            ]))),
            "secondary_roles": [{
                "title": role.role,
                "company": role.company or "",
                "location": role.location or "",
                "period": role._get_period_label(),
            } for role in secondary_roles],
            "research_groups": [{
                "organisation": split_organisation(role.company)[0] or role.role,
                "role": role.role if role.company else "",
                "meta": " / ".join(filter(None, [split_organisation(role.company)[1], role.location,
                                                 role._get_period_label()])),
                "period": role._get_period_label(),
                "items": [{"name": project.name, "technologies": ", ".join(project.technology_ids.mapped("name"))}
                          for project in role.project_ids.filtered("is_public")],
            } for role in research_roles],
            "skills": [{"name": group.name, "items": " / ".join(group.technology_ids.mapped("name")),
                        "technology_names": group.technology_ids.mapped("name"),
                        "icon": skill_icon(group.with_context(lang="en_US").name)}
                       for group in self.skill_group_ids.filtered("is_public")],
            "education": [{
                "qualification": entry.qualification,
                "title": split_qualification(entry.qualification)[0],
                "specialisation": split_qualification(entry.qualification)[1],
                "year": str(entry.year_end or entry.year_start or ""),
                "meta": " / ".join(filter(None, [
                    entry.code,
                    ", ".join(filter(None, [entry.institution, entry.location])),
                    entry._get_period_label() if entry.year_start else "",
                    " ".join(filter(None, [selection_label(entry, "status") if entry.status else "",
                                           str(entry.year_end) if entry.year_end and not entry.year_start else ""])),
                ])),
            } for entry in education],
            "trainings": [{
                "name": training.name,
                "meta": " / ".join(filter(None, [training.issuer,
                                                 selection_label(training, "status") if training.status else ""])),
                "year": str(training.year) if training.year else "",
                "is_current": training.status == "current",
            } for training in self.training_ids.filtered("is_public")],
            "languages": [{
                "name": language.name,
                "level": (selection_label(language, "level").split(" · ")[0] if language.level else ""),
                "percent": LANGUAGE_LEVEL_PERCENT.get(language.level, 0),
            } for language in self.spoken_language_ids.filtered("is_public")],
            "volunteering": [{
                "title": entry.title,
                "meta": " / ".join(filter(None, [entry.organisation, entry.location, en_dash_ranges(entry.period)])),
                "highlight": first_line(entry.highlights),
                "recognitions": entry._get_recognition_lines(),
            } for entry in self.volunteering_ids.filtered("is_public")],
        }

    def _get_case_study_values(self, project):
        """The case-study page of one of the profile's featured projects shown on the portfolio."""
        self.ensure_one()
        featured = self.project_ids.filtered(lambda p: p.is_public and p.is_featured)
        position = featured.ids.index(project.id)
        role = project.experience_id
        text = " ".join((project.description or "").split())
        lead = first_sentence(text)

        def neighbour(other):
            return {
                "name": other.name,
                "url": other._get_portfolio_path(),
                "index": f"{featured.ids.index(other.id) + 1:02d}",
                "cover_url": f"/portfolio/project/{other.id}/cover" if other.cover_image else None,
            } if other != project else None

        return {
            "name": project.name,
            "subtitle": capitalize_first(project.subtitle),
            "area": project.area or "",
            "index": f"{position + 1:02d}",
            "count": f"{len(featured):02d}",
            "lead": lead,
            "overview": text[len(lead):].strip(),
            "facts": [(label, value) for label, value in (
                (self.env._("Role"), role.role if role else ""),
                (self.env._("Company"), role.company if role else ""),
                (self.env._("Period"), role._get_period_label() if role else ""),
                (self.env._("Platforms"), project.platforms or ""),
            ) if value],
            "cover_url": f"/portfolio/project/{project.id}/cover" if project.cover_image else None,
            "metrics": [{"value": metric.value, "label": metric.label} for metric in project.metric_ids],
            "highlights": titled_items(project.highlights),
            "steps": [{"name": step.name, "detail": step.detail or "", "is_highlighted": step.is_highlighted}
                      for step in project.step_ids],
            "technology_names": project.technology_ids.mapped("name"),
            "url": project._get_url(),
            "previous": neighbour(featured[position - 1]),
            "next": neighbour(featured[(position + 1) % len(featured)]),
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
                        page_texts.append(page_text(page))
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
