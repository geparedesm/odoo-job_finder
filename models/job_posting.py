"""Job postings collected from external sources."""

from odoo import fields, models


class JobPosting(models.Model):
    _name = "job.posting"
    _description = "Oferta de empleo"

    title = fields.Char(string="Título")
    company = fields.Char(string="Empresa")
    description = fields.Text(string="Descripción")
    location = fields.Char(string="Ubicación")
    source_url = fields.Char(string="URL de origen")
    date_posted = fields.Date(string="Fecha de publicación")
