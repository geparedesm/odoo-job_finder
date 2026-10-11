"""Job postings collected from external sources."""

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import SQL

from .cv_adapter import adapt_profile
from .job_matcher import score_job


class JobPosting(models.Model):
    _name = "job.posting"
    _description = "Oferta de empleo"
    _order = "id"

    title = fields.Char(string="Título")
    company = fields.Char(string="Empresa")
    description = fields.Text(string="Descripción")
    location = fields.Char(string="Ubicación")
    source_url = fields.Char(string="URL de origen")
    date_posted = fields.Date(string="Fecha de publicación")

    source = fields.Char(string="Proveedor", index=True)
    external_id = fields.Char(string="ID externo", index=True)
    url = fields.Char(related="source_url", readonly=False)
    posted_date = fields.Date(related="date_posted", readonly=False)
    match_score = fields.Integer(string="Coincidencia", compute="_compute_match_score")

    _sql_constraints = [
        ("source_external_uniq", "unique(source, external_id)", "La oferta ya existe."),
    ]

    @api.depends("title", "description")
    @api.depends_context("uid")
    def _compute_match_score(self):
        profile = self.env["job.profile"].search([("user_id", "=", self.env.uid)], limit=1)
        values = {name: profile[name] for name in ("summary", "skills", "experience")} if profile else {}
        for posting in self:
            posting.match_score = score_job(values, "\n".join((posting.title or "", posting.description or "")))

    def _order_to_sql(self, order, query, alias=None, reverse=False):
        ordered_ids = self.env.context.get("related_job_ids")
        if ordered_ids and (order or self._order).lower() in ("id", "id asc"):
            # An IN domain loses ranking; apply it in SQL before pagination.
            return SQL(
                "array_position(%s::int[], %s) %s",
                [int(record_id) for record_id in ordered_ids],
                SQL.identifier(alias or self._table, "id"),
                SQL("DESC" if reverse else "ASC"),
            )
        return super()._order_to_sql(order, query, alias=alias, reverse=reverse)

    def action_search_online_jobs(self):
        return self.env["job.profile"].action_search_online_jobs()

    def action_adapt_cv(self):
        self.ensure_one()
        profile = self.env["job.profile"].search([("user_id", "=", self.env.uid)], limit=1)
        if not profile:
            raise UserError("Cree su perfil profesional antes de adaptar el CV.")
        adapted = adapt_profile(
            {name: profile[name] for name in ("summary", "skills", "experience")},
            self.description or "",
        )
        profile.write({
            "adapted_summary": adapted["summary"],
            "adapted_skills": adapted["skills"],
        })
        return profile.action_open_my_profile()
