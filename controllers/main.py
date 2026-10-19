"""Public portfolio website page, its photo, and the CV download."""

import re

from werkzeug.exceptions import Forbidden, NotFound

from odoo import http
from odoo.http import content_disposition, request


def published_profile():
    """The profile published as the portfolio, read with minimal sudo: visitors cannot read profiles."""
    return request.env["job.profile"].sudo().search([("is_published_as_portfolio", "=", True)], limit=1)


def cv_filename(full_name):
    """A download name built from the profile name without quotes, separators or control characters."""
    name = " ".join(re.sub(r"[^\w .-]+", " ", full_name or "").split())
    return (name or "portfolio") + "-cv.pdf"


class Portfolio(http.Controller):

    @http.route("/portfolio", type="http", auth="public", website=True, sitemap=True)
    def portfolio(self, **kw):
        """The portfolio page (the website's homepage): the published profile's public entries."""
        profile = published_profile()
        values = {
            "profile": profile,
            "portfolio": profile._get_portfolio_values() if profile else {},
            "main_object": profile,
        }
        return request.render("job_finder.portfolio_page", values)

    @http.route("/portfolio/photo", type="http", auth="public", website=True, sitemap=False)
    def portfolio_photo(self, **kw):
        """Only the published profile's photo is public."""
        profile = published_profile()
        if not profile or not profile.photo:
            raise NotFound()
        stream = request.env["ir.binary"]._get_image_stream_from(profile, "photo", width=1024, height=1024)
        return stream.get_response(max_age=3600)

    @http.route("/portfolio/cv", type="http", auth="user", website=True, sitemap=False)
    def download_cv(self, **kw):
        """Download the published profile's CV as PDF (internal users only)."""
        if not request.env.user._is_internal():
            raise Forbidden("The CV is available to internal users only.")
        profile = published_profile()
        if not profile:
            raise NotFound("No portfolio published.")
        # Minimal sudo: any internal user can download the published owner's CV.
        pdf_content, _filename = request.env["ir.actions.report"].sudo()._render_qweb_pdf(
            "job_finder.report_job_profile", profile.ids
        )
        return request.make_response(
            pdf_content,
            [
                ("Content-Type", "application/pdf"),
                ("Content-Disposition", content_disposition(cv_filename(profile.full_name))),
            ],
        )
