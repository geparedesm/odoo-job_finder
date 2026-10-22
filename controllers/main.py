"""Public portfolio website: its page, the case-study pages, their images, and the CV download."""

import re

from werkzeug.exceptions import NotFound

from odoo import http
from odoo.http import content_disposition, request


def published_profile():
    """The profile published as the portfolio, read with minimal sudo: visitors cannot read profiles."""
    return request.env["job.profile"].sudo().search([("is_published_as_portfolio", "=", True)], limit=1)


def published_project(profile, project_id):
    """A featured project shown on the published portfolio, or an empty recordset."""
    return profile.project_ids.filtered(lambda p: p.id == project_id and p.is_public and p.is_featured)


def cv_filename(full_name, areas=()):
    """A download name built from the profile name (and the CV areas) without quotes, separators or control
    characters."""
    name = " ".join(re.sub(r"[^\w .-]+", " ", " ".join([full_name or "", *areas])).split())
    return (name or "portfolio") + "-cv.pdf"


class Portfolio(http.Controller):

    def _layout_values(self, profile):
        """Values shared by every portfolio page: navigation, contact links and the CV button state."""
        return {
            "profile": profile,
            "portfolio": profile._get_portfolio_values() if profile else {},
            "is_cv_locked": request.env.user._is_public(),
            "is_internal_user": request.env.user._is_internal(),
        }

    @http.route("/portfolio", type="http", auth="public", website=True, sitemap=True)
    def portfolio(self, **kw):
        """The portfolio page (the website's homepage): the published profile's public entries."""
        profile = published_profile()
        values = {
            **self._layout_values(profile),
            "main_object": profile,
            # Explicit: website.layout only derives it from main_object when no page title is given.
            "seo_object": profile,
        }
        return request.render("job_finder.portfolio_page", values)

    @http.route("/portfolio/project/<string:slug>", type="http", auth="public", website=True, sitemap=False)
    def case_study(self, slug, **kw):
        """The case-study page of a featured project; other projects are not public pages."""
        profile = published_profile()
        _name, project_id = request.env["ir.http"]._unslug(slug)
        project = published_project(profile, project_id) if profile and project_id else None
        if not project:
            raise NotFound()
        if slug != request.env["ir.http"]._slug(project):
            # An old or shortened slug: send search engines and visitors to the current address.
            return request.redirect(project._get_portfolio_path(), code=301)
        return request.render("job_finder.case_study_page", {
            **self._layout_values(profile),
            "case": profile._get_case_study_values(project),
        })

    @http.route("/portfolio/photo", type="http", auth="public", website=True, sitemap=False)
    def portfolio_photo(self, **kw):
        """Only the published profile's photo is public."""
        profile = published_profile()
        if not profile or not profile.photo:
            raise NotFound()
        stream = request.env["ir.binary"]._get_image_stream_from(profile, "photo", width=1024, height=1024)
        return stream.get_response(max_age=3600)

    @http.route("/portfolio/project/<int:project_id>/cover", type="http", auth="public", website=True, sitemap=False)
    def project_cover(self, project_id, **kw):
        """Only the covers of featured projects shown on the published portfolio are public."""
        profile = published_profile()
        project = published_project(profile, project_id) if profile else None
        if not project or not project.cover_image:
            raise NotFound()
        stream = request.env["ir.binary"]._get_image_stream_from(project, "cover_image", width=1920, height=1920)
        return stream.get_response(max_age=3600)

    # Deliberately public: visitors get a sign-in page and portal users an explanation instead of a bare redirect or
    # error. Only internal users receive the PDF.
    @http.route("/portfolio/cv", type="http", auth="public", website=True, sitemap=False)
    def download_cv(self, **kw):
        """Download the published profile's CV as PDF (internal users only)."""
        profile = published_profile()
        if not profile:
            raise NotFound("No portfolio published.")
        if request.env.user._is_public():
            return request.render("job_finder.cv_sign_in_page", self._layout_values(profile))
        if not request.env.user._is_internal():
            return request.render("job_finder.cv_unavailable_page", self._layout_values(profile), status=403)
        areas = profile.cv_area_ids
        if areas and "download" not in kw:
            # A profile with CV areas lets the user choose the CV first.
            return request.render("job_finder.cv_choose_page", {
                **self._layout_values(profile),
                "areas": [{"id": area.id, "name": area.name, "headline": area.headline or ""} for area in areas],
            })
        # Only areas of the published profile count; other values are ignored.
        chosen = areas.filtered(lambda area: str(area.id) in request.httprequest.args.getlist("area"))
        # Minimal sudo: any internal user can download the published owner's CV.
        pdf_content, _filename = request.env["ir.actions.report"].sudo()._render_qweb_pdf(
            "job_finder.report_job_profile", profile.ids, data={"area_ids": chosen.ids},
        )
        return request.make_response(
            pdf_content,
            [
                ("Content-Type", "application/pdf"),
                ("Content-Disposition", content_disposition(cv_filename(profile.full_name, chosen.mapped("name")))),
            ],
        )
