"""Administrator-managed job provider credentials."""
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    adzuna_app_id = fields.Char(string="Adzuna App ID", config_parameter="adzuna_app_id", groups="base.group_system")
    adzuna_app_key = fields.Char(string="Adzuna App Key", config_parameter="adzuna_app_key", groups="base.group_system")
    adzuna_country = fields.Char(string="Adzuna country code", default="gb", config_parameter="adzuna_country", groups="base.group_system")
    jooble_api_key = fields.Char(string="Jooble API Key", config_parameter="jooble_api_key", groups="base.group_system")
