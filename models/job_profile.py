"""User profiles populated from uploaded CVs."""

import base64
from io import BytesIO

from odoo import fields, models
from odoo.exceptions import UserError

from .cv_parser import parse_cv_text
from .job_matcher import score_job
from .job_board_connector import fetch_jobs, search_query


class JobProfile(models.Model):
    _name = "job.profile"
    _description = "Perfil profesional"

    _sql_constraints = [
        ("user_uniq", "unique(user_id)", "Ya existe un perfil para este usuario."),
    ]

    user_id = fields.Many2one(
        "res.users", string="Usuario", required=True,
        default=lambda self: self.env.user, ondelete="cascade",
    )
    full_name = fields.Char(string="Nombre completo")
    headline = fields.Char(string="Título profesional")
    email = fields.Char(string="Correo electrónico")
    phone = fields.Char(string="Teléfono")
    location = fields.Char(string="Ubicación")
    linkedin = fields.Char(string="LinkedIn")
    summary = fields.Text(string="Resumen")
    skills = fields.Text(string="Habilidades")
    experience = fields.Text(string="Experiencia")
    education = fields.Text(string="Educación")
    certifications = fields.Text(string="Certificaciones")
    languages = fields.Text(string="Idiomas")
    extra_info = fields.Text(string="Información adicional")
    adapted_summary = fields.Text(string="Resumen adaptado", readonly=True)
    adapted_skills = fields.Text(string="Habilidades adaptadas", readonly=True)
    cv_file = fields.Binary(string="CV en PDF")
    cv_filename = fields.Char(string="Nombre del archivo")
    cv_raw_text = fields.Text(string="Texto extraído del CV", readonly=True)
    cv_parsed_date = fields.Datetime(string="Fecha de análisis", readonly=True)

    def action_open_my_profile(self):
        profile = self.search([("user_id", "=", self.env.uid)], limit=1)
        if not profile:
            profile = self.create({"user_id": self.env.uid})
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
            "full_name", "headline", "email", "phone", "location", "linkedin",
            "summary", "skills", "experience", "education", "certifications",
            "languages",
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

    def action_search_related_jobs(self):
        self.ensure_one()
        profile = {name: self[name] for name in ("summary", "skills", "experience")}
        postings = self.env["job.posting"].search([])
        ordered_ids = postings.sorted(
            key=lambda posting: score_job(
                profile, "\n".join((posting.title or "", posting.description or "")),
            ), reverse=True,
        ).ids
        action = self.env["ir.actions.act_window"]._for_xml_id("job_finder.action_job_postings")
        action.update(
            domain=[("id", "in", ordered_ids)],
            context=dict(self.env.context, related_job_ids=ordered_ids),
        )
        return action

    def action_search_online_jobs(self):
        """Import trusted provider data into the shared, read-only user catalog."""
        from psycopg2.errors import UniqueViolation

        profile = self.search([("user_id", "=", self.env.uid)], limit=1)
        if not profile:
            raise UserError("Cree su perfil profesional antes de buscar ofertas.")
        query = search_query(profile.skills or profile.headline or profile.summary or "")
        config = self.env["ir.config_parameter"].sudo()
        # Users cannot edit the catalog; only normalized HTTP results are elevated.
        postings = self.env["job.posting"].sudo()
        ids = set()
        results = fetch_jobs(config, query, profile.location or "")
        # Collapse duplicate feed rows and prefetch existing records in one query.
        values_by_key = {(row["source"], row["external_id"]): row for row in results}
        existing = postings.search([
            ("source", "in", list({key[0] for key in values_by_key})),
            ("external_id", "in", list({key[1] for key in values_by_key})),
        ]) if values_by_key else []
        by_key = {(job.source, job.external_id): job for job in existing}
        for key, values in values_by_key.items():
            posting = by_key.get(key)
            if posting:
                posting.write(values)
            else:
                try:
                    with self.env.cr.savepoint():
                        posting = postings.create(values)
                except UniqueViolation:
                    posting = postings.search([
                        ("source", "=", key[0]), ("external_id", "=", key[1]),
                    ], limit=1)
                    if not posting:
                        raise
                    posting.write(values)
            ids.add(posting.id)
        profile_values = {name: profile[name] for name in ("summary", "skills", "experience")}
        records = self.env["job.posting"].browse(sorted(ids))
        ordered_ids = records.sorted(key=lambda job: score_job(
            profile_values, "\n".join((job.title or "", job.description or "")),
        ), reverse=True).ids
        action = self.env["ir.actions.act_window"]._for_xml_id("job_finder.action_job_postings")
        action.update(domain=[("id", "in", ordered_ids)],
                      context=dict(self.env.context, related_job_ids=ordered_ids))
        return action
