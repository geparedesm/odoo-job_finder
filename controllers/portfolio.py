"""Public portfolio pages."""

import re

from odoo import http
from odoo.http import request
from werkzeug.exceptions import NotFound


_PORTFOLIO_SLUG_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


class PortfolioController(http.Controller):
    """Serve a user's public professional profile."""

    @http.route(
        "/portfolio/<string:slug>", type="http", auth="public", website=True, sitemap=True,
    )
    def portfolio(self, slug):
        """Render the portfolio belonging to ``slug`` or return a 404."""
        if not _PORTFOLIO_SLUG_PATTERN.fullmatch(slug):
            raise NotFound()

        # Public portfolios intentionally expose only fields selected by the
        # template. sudo is limited to these read-only lookups because a
        # public visitor has no model access to users or private profiles.
        user = request.env["res.users"].sudo().search(
            [("portfolio_slug", "=", slug)], limit=1,
        )
        if not user:
            raise NotFound()
        profile = request.env["job.profile"].sudo().search(
            [("user_id", "=", user.id)], limit=1,
        )
        if not profile:
            raise NotFound()

        return request.render(
            "job_finder.portfolio_page",
            {"portfolio_user": user, "profile": profile},
        )
