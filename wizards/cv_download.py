"""Download a CV for some of the profile's CV areas, or the complete one."""

from odoo import fields, models


class CvDownload(models.TransientModel):
    _name = "job_finder.cv_download"
    _description = "Download CV"

    profile_id = fields.Many2one("job.profile", string="Profile", required=True, ondelete="cascade")
    area_ids = fields.Many2many(
        "job_finder.cv_area", string="Areas", domain="[('profile_id', '=', profile_id)]",
        help="Leave empty for the complete CV.",
    )

    def action_download(self):
        self.ensure_one()
        return self.env.ref("job_finder.action_report_job_profile").report_action(
            self.profile_id, data={
                # The client downloads a report with data without ids in its URL: the profile goes in the data.
                "profile_ids": self.profile_id.ids,
                "area_ids": (self.area_ids & self.profile_id.cv_area_ids).ids,
            },
        )
