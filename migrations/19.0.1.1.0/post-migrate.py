"""Build the structured profile records from the CV sections stored as text before 19.0.1.1.0."""

from odoo import SUPERUSER_ID, api

SECTIONS = ("experience", "projects", "skills", "education", "trainings", "volunteering", "languages")


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for profile in env["job.profile"].search([]):
        if profile.experience_ids or profile.skill_group_ids or profile.education_ids:
            continue  # already structured; never overwrite a person's edits
        sections = {name: profile[name] for name in SECTIONS if profile[name]}
        if sections:
            profile._set_structured_sections(sections)
