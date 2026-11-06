"""Owned offers and the narrowly scoped external evaluation contract."""

import json
import math
from datetime import datetime, timedelta
from urllib.parse import urlparse

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

from .offer_scoring import score_offer, usage_years


class JobOffer(models.Model):
    _name = "job_finder.job_offer"
    _description = "Job offer"
    _rec_name = "title"
    _order = "rule_score desc, id desc"

    _identity_unique = models.Constraint("UNIQUE(profile_id, adzuna_id)", "This offer already exists for this profile.")

    profile_id = fields.Many2one("job.profile", string="Profile", required=True, ondelete="cascade")
    search_id = fields.Many2one("job_finder.job_search", string="Search", required=True, ondelete="restrict")
    cv_area_id = fields.Many2one("job_finder.cv_area", string="CV area", required=True, ondelete="restrict")
    adzuna_id = fields.Char(string="Adzuna ID", required=True, index=True)
    title = fields.Char(string="Offer", required=True)
    company = fields.Char(string="Company")
    location = fields.Char(string="Location")
    salary_min = fields.Float(string="Minimum salary")
    salary_max = fields.Float(string="Maximum salary")
    is_salary_predicted = fields.Boolean(string="Predicted salary")
    contract_type = fields.Char(string="Contract type")
    contract_time = fields.Char(string="Contract time")
    category = fields.Char(string="Category")
    posted_at = fields.Datetime(string="Posted date")
    snippet = fields.Text(string="Snippet")
    url = fields.Char(string="Offer link")
    source_url = fields.Char(string="Adzuna", default="https://www.adzuna.com.au", readonly=True)
    rule_score = fields.Integer(string="Rule score", readonly=True)
    score_breakdown = fields.Text(string="Score breakdown", readonly=True)
    state = fields.Selection([(key, label) for key, label in (
        ("new", "New"), ("saved", "Saved"), ("applied", "Applied"), ("interview", "Interview"),
        ("offer", "Offer"), ("rejected", "Rejected"), ("discarded", "Discarded"))],
        string="Status", required=True, default="new")
    discard_reason = fields.Text(string="Discard reason")
    rejection_reason = fields.Text(string="Rejection reason")
    notes = fields.Text(string="Notes")
    status_changed_at = fields.Datetime(string="Status changed", readonly=True)
    applied_at = fields.Datetime(string="Applied date", readonly=True)
    interview_at = fields.Datetime(string="Interview date", readonly=True)
    ai_state = fields.Selection([("pending", "Pending"), ("done", "Done"), ("error", "Error")],
                                string="AI state", readonly=True)
    ai_score = fields.Float(string="AI score", readonly=True)
    ai_fit = fields.Text(string="Fit", readonly=True)
    ai_gaps = fields.Text(string="Gaps", readonly=True)
    ai_warnings = fields.Text(string="Warnings", readonly=True)
    ai_evaluated_at = fields.Datetime(string="Evaluated at", readonly=True)

    def _check_access(self, operation):
        if not self.env.su and self.env.user.has_group("job_finder.group_job_finder_evaluator"):
            return self, lambda: AccessError(self.env._("Evaluators may use only the evaluation interface."))
        return super()._check_access(operation)

    @api.constrains("profile_id", "cv_area_id", "search_id", "state", "discard_reason", "rejection_reason")
    def _check_relations(self):
        for offer in self:
            if offer.cv_area_id.profile_id != offer.profile_id or offer.search_id.profile_id != offer.profile_id:
                raise ValidationError(self.env._("Offer relations must belong to the same profile."))
            if offer.search_id.cv_area_id != offer.cv_area_id:
                raise ValidationError(self.env._("The offer area must match its search."))
            if offer.state == "discarded" and not offer.discard_reason:
                raise ValidationError(self.env._("A discard reason is required."))
            if offer.state == "rejected" and not offer.rejection_reason:
                raise ValidationError(self.env._("A rejection reason is required."))

    def write(self, vals):
        if "state" in vals:
            vals = dict(vals, status_changed_at=fields.Datetime.now())
            if vals["state"] in ("applied", "interview"):
                vals[vals["state"] + "_at"] = fields.Datetime.now()
        return super().write(vals)

    @api.model
    def action_propose_searches(self):
        return self.env["job_finder.job_search"].action_propose_searches()

    @api.model
    def action_search_now(self):
        return self.env["job_finder.job_search"].action_search_now()

    def _reason_dialog(self, view):
        self.ensure_one()
        self.check_access("write")
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": self.id,
                "view_mode": "form", "views": [(self.env.ref("job_finder." + view).id, "form")],
                "target": "new"}

    def action_discard(self):
        return self._reason_dialog("view_job_offer_discard")

    def action_reject(self):
        return self._reason_dialog("view_job_offer_reject")

    def action_confirm_discard(self):
        self.write({"state": "discarded"})
        return {"type": "ir.actions.act_window_close"}

    def action_confirm_reject(self):
        self.write({"state": "rejected"})
        return {"type": "ir.actions.act_window_close"}

    @api.model
    def _provider_values(self, search, row):
        try:
            posted = datetime.fromisoformat(row["created"].replace("Z", "+00:00")).replace(tzinfo=None)
        except (KeyError, TypeError, ValueError, AttributeError):
            return None
        if posted < fields.Datetime.now() - timedelta(days=search.profile_id.max_offer_age):
            return None
        snippet = row.get("description", "")
        if not isinstance(snippet, str):
            return None
        profile = search.profile_id
        technologies = {}
        for project in profile.project_ids:
            role = project.experience_id
            recent = role.is_current or (role.date_end and (fields.Date.today() - role.date_end).days <= 730)
            for technology in project.technology_ids:
                technologies[technology.name] = max(technologies.get(technology.name, 0), 20 if recent else 10)
        for technology in profile.skill_group_ids.technology_ids:
            technologies.setdefault(technology.name, 8)
        location = row.get("location", {}).get("display_name", "") if isinstance(row.get("location"), dict) else ""
        location_data = row.get("location") if isinstance(row.get("location"), dict) else {}
        location_areas = location_data.get("area", [])
        if not isinstance(location_areas, list):
            location_areas = []
        location_areas = [area for area in location_areas if isinstance(area, str)]
        targets = [city.strip() for city in (search.cities or "").split(",") if city.strip()]
        if search.is_australia:
            targets.append("Australia")
        if search.is_remote:
            targets.append("remote")
        area_terms = [search.cv_area_id.name, search.cv_area_id.headline]
        area_terms += [word for word in search.cv_area_id.name.split() if len(word) > 2]
        score, parts, reason = score_offer(row["title"], snippet, area_terms,
                                           technologies, " ".join([location, *location_areas]), target=targets)
        if not reason and score < profile.score_threshold:
            reason = "Below score threshold"
        reasons = {
            "Australian citizenship or permanent residency required": self.env._("Australian citizenship or permanent residency required"),
            "Security clearance required": self.env._("Security clearance required"),
            "Excluded seniority": self.env._("Excluded seniority"),
            "Below score threshold": self.env._("Below score threshold"),
        }
        url = row.get("redirect_url", "")
        if not isinstance(url, str) or urlparse(url).scheme not in ("http", "https"):
            url = ""
        def label(key, field):
            value = row.get(key)
            result = value.get(field, "") if isinstance(value, dict) else ""
            return result[:500] if isinstance(result, str) else ""
        def salary(key):
            value = row.get(key, 0)
            return value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else 0
        return dict(profile_id=profile.id, search_id=search.id, cv_area_id=search.cv_area_id.id,
                    adzuna_id=row["id"][:200], title=row["title"][:500], company=label("company", "display_name"),
                    location=location, salary_min=salary("salary_min"), salary_max=salary("salary_max"),
                    is_salary_predicted=row.get("salary_is_predicted") in (1, "1"),
                    contract_type=row.get("contract_type") if isinstance(row.get("contract_type"), str) else "",
                    contract_time=row.get("contract_time") if isinstance(row.get("contract_time"), str) else "",
                    category=label("category", "label"), posted_at=posted, snippet=snippet[:20000], url=url,
                    rule_score=score, score_breakdown=json.dumps(parts, sort_keys=True),
                    state="discarded" if reason else "new", discard_reason=reasons.get(reason, ""),
                    ai_state=False if reason else "pending")

    def _refuse_evaluator_metadata(self):
        if not self.env.su and self.env.user.has_group("job_finder.group_job_finder_evaluator"):
            raise AccessError(self.env._("Evaluators may use only the evaluation interface."))

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        self._refuse_evaluator_metadata()
        return super().fields_get(allfields=allfields, attributes=attributes)

    @api.model
    def default_get(self, fields_list):
        self._refuse_evaluator_metadata()
        return super().default_get(fields_list)

    @api.model
    def _check_evaluator(self):
        if not self.env.user.has_group("job_finder.group_job_finder_evaluator"):
            raise AccessError(self.env._("Only Job Finder evaluators may use this interface."))

    def _profile_summary(self):
        self.ensure_one()
        profile = self.profile_id
        technologies = profile.project_ids.technology_ids | profile.skill_group_ids.technology_ids
        summaries = []
        for technology in technologies[:30]:
            roles = profile.project_ids.filtered(lambda project, technology=technology: technology in project.technology_ids).experience_id
            intervals = [(role.date_start, fields.Date.today() if role.is_current else role.date_end) for role in roles]
            known = [(start, end) for start, end in intervals if start and end]
            summaries.append({"name": technology.name[:200], "years": usage_years(known) if known else None,
                              "has_unknown_periods": not intervals or len(known) != len(intervals)})
        return {"headline": (profile.headline or "")[:500], "areas": [name[:200] for name in profile.cv_area_ids.mapped("name")[:20]],
                "technologies": summaries, "visa": (profile.visa_status or "")[:500], "work_rights_until": str(profile.work_rights_until),
                "location": (profile.location or "")[:500]}

    @api.model
    def evaluator_pending(self, limit=10):
        """The only queue read interface for external evaluators."""
        self._check_evaluator()
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValidationError(self.env._("Limit must be an integer from 1 to 100."))
        # Evaluators have no CRUD ACL; expose only bounded queue payloads after checking their dedicated group.
        offers = self.sudo().search([("ai_state", "=", "pending"), ("state", "!=", "discarded")], limit=limit)
        return [{"id": offer.id, "title": offer.title, "snippet": offer.snippet, "rule_score": offer.rule_score,
                 "profile": offer._profile_summary()} for offer in offers]

    @api.model
    def evaluator_store_result(self, offer_id, result):
        """Validate every input before the narrowly privileged queue update."""
        self._check_evaluator()
        if type(offer_id) is not int or offer_id < 1 or type(result) is not dict:
            raise ValidationError(self.env._("Invalid evaluator input."))
        if set(result) != {"ai_state", "ai_score", "ai_fit", "ai_gaps", "ai_warnings"}:
            raise ValidationError(self.env._("Invalid evaluator fields."))
        score = result["ai_score"]
        if type(score) not in (int, float) or not 0 <= score <= 100 or not math.isfinite(score):
            raise ValidationError(self.env._("AI score must be a finite number from 0 to 100."))
        if type(result["ai_state"]) is not str or result["ai_state"] not in ("done", "error"):
            raise ValidationError(self.env._("AI state must be done or error."))
        for field in ("ai_fit", "ai_gaps", "ai_warnings"):
            if type(result[field]) is not str or len(result[field]) > 10000:
                raise ValidationError(self.env._("AI text must be a string of at most 10000 characters."))
        # ACL-free evaluator updates are restricted to the validated pending offer and the five result fields.
        self.env.cr.execute("SELECT id FROM job_finder_job_offer WHERE id = %s FOR UPDATE", [offer_id])
        offer = self.sudo().browse(offer_id).exists()
        offer.invalidate_recordset(["ai_state"])
        if not offer or offer.ai_state != "pending" or offer.state == "discarded":
            raise ValidationError(self.env._("Only pending offers can be evaluated."))
        offer.write(dict(result, ai_evaluated_at=fields.Datetime.now()))
        return True
