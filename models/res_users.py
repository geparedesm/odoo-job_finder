"""Public portfolio URL slugs for users."""

import re
import unicodedata

from odoo import api, fields, models


def _portfolio_slug(value):
    """Return a stable, URL-safe slug from a user name or login."""
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value or "portfolio"


class ResUsers(models.Model):
    _inherit = "res.users"

    portfolio_slug = fields.Char(
        string="Portfolio URL slug", copy=False, index=True,
    )

    @classmethod
    def _generate_portfolio_slug(cls, values):
        return _portfolio_slug(values.get("portfolio_slug") or values.get("name") or values.get("login"))

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        return users

    def _ensure_portfolio_slugs(self):
        for user in self.filtered(lambda record: not record.portfolio_slug):
            base = _portfolio_slug(user.login or user.name)
            slug = base
            if self.search_count([("portfolio_slug", "=", slug), ("id", "!=", user.id)]):
                slug = f"{base}-{user.id}"
            user.portfolio_slug = slug
