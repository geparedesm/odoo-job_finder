"""User profiles populated from uploaded CVs."""

import base64
from io import BytesIO

from odoo import fields, models
from odoo.exceptions import UserError

from .cv_parser import parse_cv_text


class JobProfile(models.Model):
    _name = "job.profile"
    _description = "Perfil profesional"

    # Odoo 19 declares table constraints as models.Constraint; _sql_constraints is no longer applied.
    _user_uniq = models.Constraint("UNIQUE (user_id)", "A profile already exists for this user.")

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
    volunteering = fields.Text(
        string="Volunteering", help="Leadership and volunteering experience from the CV.",
    )
    projects = fields.Text(
        string="Projects", help="Academic research and projects from the CV.",
    )
    trainings = fields.Text(
        string="Trainings", help="Training and credentials from the CV.",
    )
    extra_info = fields.Text(string="Información adicional")
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
            "languages", "volunteering", "projects", "trainings", "extra_info",
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
