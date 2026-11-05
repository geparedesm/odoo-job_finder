"""Editable area searches and fairly scheduled, budgeted ingestion."""

import logging

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .adzuna_client import AdzunaClient, ProviderError

_logger = logging.getLogger(__name__)


class JobSearch(models.Model):
    _name = "job_finder.job_search"
    _description = "Job search"
    _rec_name = "cv_area_id"
    _order = "last_run_at asc nulls first, id"

    _area_unique = models.Constraint("UNIQUE(cv_area_id)", "A search already exists for this CV area.")

    profile_id = fields.Many2one("job.profile", string="Profile", required=True, ondelete="cascade")
    cv_area_id = fields.Many2one("job_finder.cv_area", string="CV area", required=True, ondelete="cascade")
    is_active = fields.Boolean(string="Active", default=True)
    keywords = fields.Char(string="Keywords", required=True)
    cities = fields.Char(string="Cities", default="Perth", help="One or more cities, separated by commas.")
    is_remote = fields.Boolean(string="Remote")
    is_australia = fields.Boolean(string="All of Australia")
    last_run_at = fields.Datetime(string="Last run", readonly=True)
    last_run_info = fields.Char(string="Last run status", readonly=True)

    def _check_access(self, operation):
        if not self.env.su and self.env.user.has_group("job_finder.group_job_finder_evaluator"):
            return self, lambda: AccessError(self.env._("Evaluators may use only the evaluation interface."))
        return super()._check_access(operation)

    @api.constrains("profile_id", "cv_area_id")
    def _check_profile(self):
        for search in self:
            if search.cv_area_id.profile_id != search.profile_id:
                raise ValidationError(self.env._("The search and area must belong to the same profile."))

    @api.model
    def action_propose_searches(self):
        """Create missing searches only, leaving all user edits untouched."""
        areas = self.env["job_finder.cv_area"].search([("profile_id.user_id", "=", self.env.uid)])
        existing = self.search([("cv_area_id", "in", areas.ids)]).cv_area_id
        roles = self.env["job_finder.experience"].search([("profile_id", "in", areas.profile_id.ids)])
        projects = self.env["job_finder.project"].search([("profile_id", "in", areas.profile_id.ids)])
        skills = self.env["job_finder.skill_group"].search([("profile_id", "in", areas.profile_id.ids)])
        values = []
        for area in areas - existing:
            tagged_roles = roles.filtered(lambda role, area=area: area in role.cv_area_ids)
            tagged_projects = projects.filtered(lambda project, area=area: area in project.cv_area_ids)
            terms = [area.name, area.headline, *tagged_roles.mapped("role"), *tagged_projects.mapped("name"),
                     *tagged_projects.technology_ids.mapped("name"),
                     *skills.filtered(lambda skill, area=area: area in skill.cv_area_ids).technology_ids.mapped("name")]
            keywords = " ".join(dict.fromkeys(word.lower() for term in terms if term for word in term.split()))[:500]
            values.append(dict(profile_id=area.profile_id.id, cv_area_id=area.id, keywords=keywords,
                               is_active=area.name.lower() != "hospitality"))
        self.create(values)
        return True

    def action_search_now(self):
        searches = self or self.search([("is_active", "=", True)])
        return searches._run_searches()

    @api.model
    def _cron_search(self):
        return self.search([("is_active", "=", True)])._run_searches()

    def _run_searches(self):
        self.check_access("read")
        # Only these provider settings are read with elevated rights; credentials never enter diagnostics.
        params = self.env["ir.config_parameter"].sudo()
        app_id = params.get_param("job_finder.adzuna_app_id")
        app_key = params.get_param("job_finder.adzuna_app_key")
        if not app_id or not app_key:
            raise UserError(self.env._("Configure the Adzuna app ID and app key in system parameters."))
        try:
            limit = max(1, min(1000, int(params.get_param("job_finder.adzuna_call_limit", "20"))))
        except ValueError:
            raise UserError(self.env._("The Adzuna call limit must be an integer.")) from None
        client = AdzunaClient(app_id, app_key, limit)
        for search in self.sorted(key=lambda record: (record.last_run_at or fields.Datetime.to_datetime("1900-01-01"), record.id)):
            if client.calls >= limit:
                _logger.info("Adzuna search stopped: call budget reached (%s calls)", client.calls)
                break
            modes = [(city.strip(), search.keywords) for city in (search.cities or "").split(",") if city.strip()]
            if search.is_australia:
                modes.append(("", search.keywords))
            if search.is_remote:
                modes.append(("", search.keywords + " remote"))
            try:
                for city, keywords in modes:
                    if client.calls >= limit:
                        break
                    for page in range(1, limit + 1):
                        rows = client.search(keywords, city, page)
                        search._ingest(rows)
                        if len(rows) < 20 or client.calls >= limit:
                            break
            except ProviderError as error:
                search.write({"last_run_at": fields.Datetime.now(), "last_run_info": str(error)})
                _logger.warning("Adzuna search stopped: %s", error)
                break
            search.write({"last_run_at": fields.Datetime.now(), "last_run_info": self.env._("Calls used: %s", client.calls)})
        if client.calls >= limit:
            _logger.info("Adzuna search stopped: call budget reached (%s calls)", client.calls)
        return True

    def _ingest(self, rows):
        self.ensure_one()
        offers = self.env["job_finder.job_offer"]
        valid = [row for row in rows if isinstance(row, dict) and isinstance(row.get("id"), str)
                 and 0 < len(row["id"]) <= 200 and isinstance(row.get("title"), str) and row["title"].strip()]
        known = set(offers.search([("profile_id", "=", self.profile_id.id),
                                  ("adzuna_id", "in", [row["id"] for row in valid])]).mapped("adzuna_id"))
        for row in valid:
            if row["id"] in known:
                continue
            values = offers._provider_values(self, row)
            if values:
                offers.create(values)
                known.add(row["id"])
