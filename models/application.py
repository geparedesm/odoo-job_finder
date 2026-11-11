"""Job applications owned by individual users."""

from odoo import api, fields, models
from odoo.exceptions import AccessError


class Application(models.Model):
    _name = "job_finder.application"
    _description = "Job application"
    _order = "date_applied desc, id desc"

    user_id = fields.Many2one(
        "res.users", string="User", required=True, index=True,
        default=lambda self: self.env.user, ondelete="cascade",
    )
    company = fields.Char(string="Company", required=True)
    position = fields.Char(string="Position", required=True)
    date_applied = fields.Date(
        string="Application date", required=True, default=fields.Date.context_today,
    )
    status = fields.Selection(
        selection=[
            ("sent", "Sent"),
            ("under_review", "Under review"),
            ("interview", "Interview"),
            ("rejected", "Rejected"),
            ("offer_received", "Offer received"),
        ],
        string="Status", required=True, default="sent",
    )
    notes = fields.Text(string="Notes")

    def action_open_application_form(self):
        """Open a blank application form from the list header."""
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("My Applications"),
            "res_model": self._name,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "current",
        }

    @api.depends("company", "position")
    def _compute_display_name(self):
        for application in self:
            application.display_name = self.env._(
                "%(company)s - %(position)s",
                company=application.company or "",
                position=application.position or "",
            )

    @api.constrains("user_id")
    def _check_owner(self):
        # Record rules check the old owner on write, so also validate the new owner.
        if not self.env.user.has_group("base.group_system"):
            if any(application.user_id != self.env.user for application in self):
                raise AccessError(self.env._("You can only assign applications to yourself."))
