"""Group the existing roles without projects (production, hospitality…) as secondary on the redesigned portfolio."""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    # The same rule as a CV import: professional roles without projects. Each role can be changed afterwards.
    env["job_finder.experience"].search([("category", "=", "work"), ("project_ids", "=", False)]).is_secondary = True
