"""Portfolio fields added to users."""

import re
import unicodedata

from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    _portfolio_slug_uniq = models.Constraint(
        "UNIQUE (portfolio_slug)",
        "A user with this portfolio slug already exists.",
    )

    portfolio_slug = fields.Char(string="Portfolio slug")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "portfolio_slug" not in vals and vals.get("login"):
                vals["portfolio_slug"] = self._portfolio_slug_from_login(vals["login"])
        return super().create(vals_list)

    @staticmethod
    def _portfolio_slug_from_login(login):
        normalized = unicodedata.normalize("NFKD", login).encode("ascii", "ignore").decode()
        return re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
