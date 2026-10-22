"""Values of the CV PDF: complete, or for the CV areas chosen when downloading it."""

from odoo import api, models


class ReportJobProfile(models.AbstractModel):
    # Odoo looks up the values of a report in report.<module>.<template>.
    _name = "report.job_finder.report_job_profile"
    _description = "CV report"

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        # A report action with data is downloaded without ids in its URL: the profiles come in the data, or as the
        # active records of its context.
        context = data.get("context") or {}
        docids = docids or data.get("profile_ids") or (
            context.get("active_ids") if context.get("active_model") == "job.profile" else None) or []
        profiles = self.env["job.profile"].browse(docids)
        area_ids = set(data.get("area_ids") or [])
        return {
            "doc_ids": docids,
            "doc_model": "job.profile",
            "docs": profiles,
            # Only areas of each profile count: ids of other profiles' areas are ignored.
            "cvs": {profile.id: profile._get_cv_values(profile.cv_area_ids.filtered(lambda area: area.id in area_ids))
                    for profile in profiles},
        }
