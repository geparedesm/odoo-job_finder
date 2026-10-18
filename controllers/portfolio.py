"""Public portfolio page."""

from odoo import http
from odoo.http import request


class PortfolioController(http.Controller):
    @http.route("/portfolio/<string:slug>", type="http", auth="public", website=True, sitemap=True)
    def portfolio(self, slug):
        profile = request.env["job.profile"].search(
            [("portfolio_slug", "=", slug)], limit=1,
        )
        if not profile:
            return request.not_found()
        return request.render("job_finder.portfolio_page", {"profile": profile})
