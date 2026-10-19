"""Portfolio public page and CV download."""

from werkzeug.exceptions import NotFound

from odoo import http
from odoo.addons.web.controllers.home import Home
from odoo.http import request

from ..models.portfolio_content import normalize_host, parse_hosts


class PortfolioHome(Home):
    """Override web's Home.index to serve the portfolio for configured hosts."""

    @http.route("/", auth="none", website=False)
    def index(self, **kw):
        """Serve portfolio page for configured hosts, otherwise delegate to web's home."""
        host_header = normalize_host(request.httprequest.host)

        # Read the configured portfolio hosts from system parameter
        # Minimal sudo: reading a system parameter that controls a public page
        param = request.env["ir.config_parameter"].sudo().get_param(
            "job_finder.portfolio_hosts", "gp-developer.com,www.gp-developer.com"
        )
        portfolio_hosts = parse_hosts(param)

        if host_header in portfolio_hosts:
            # Serve the portfolio page for configured hosts
            # Use sudo to search for published profile (accessible to public)
            published = request.env["job.profile"].sudo().search(
                [("is_published_as_portfolio", "=", True)], limit=1
            )
            # Language selection: query param → cookie → default to en_US
            lang = request.params.get("lang")
            if not lang:
                # Try reading the stored cookie
                lang = request.httprequest.cookies.get("job_finder_portfolio_lang", "en_US")
            # Validate language against whitelist and active res.lang
            valid_langs = {"en_US", "es_ES"}
            try:
                active_langs = {l.code for l in request.env["res.lang"].search([("active", "=", True)])}
                if lang not in valid_langs.intersection(active_langs):
                    lang = "en_US"
            except Exception:
                # If we can't query active languages, just validate against whitelist
                if lang not in valid_langs:
                    lang = "en_US"

            # Render the template using QWeb with language context
            html = request.env["ir.qweb"].with_context(lang=lang)._render(
                "job_finder.portfolio_page",
                {
                    "profile": published._get_portfolio_values() if published else {},
                    "is_published": bool(published),
                    "current_lang": lang,
                },
            )
            # Set a cookie to remember the language choice
            response = request.make_response(html)
            response.set_cookie("job_finder_portfolio_lang", lang, max_age=31536000)  # 1 year
            return response
        else:
            # Fall back to web's standard behavior
            return super().index(**kw)


class PortfolioCV(http.Controller):
    """Download the published profile's complete CV PDF."""

    @http.route("/portfolio/cv", auth="user")
    def download_cv(self):
        """Download the published profile's CV as PDF."""
        # Minimal sudo: search for published profile (record rules restrict users to their own)
        published = request.env["job.profile"].sudo().search(
            [("is_published_as_portfolio", "=", True)], limit=1
        )
        if not published:
            raise NotFound("No portfolio published.")

        # Minimal sudo: any logged-in user can download the published owner's CV
        pdf_content, _filename = request.env["ir.actions.report"].sudo()._render_qweb_pdf(
            "job_finder.report_job_profile", published.ids
        )
        return request.make_response(
            pdf_content,
            [
                ("Content-Type", "application/pdf"),
                ("Content-Disposition", f'attachment; filename="{published.full_name}-cv.pdf"'),
            ],
        )
