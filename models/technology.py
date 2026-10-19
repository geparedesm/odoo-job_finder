"""Technologies and methods shared by projects and skill groups."""

from odoo import fields, models


class Technology(models.Model):
    _name = "job_finder.technology"
    _description = "Technology or method"
    _order = "name"

    _name_uniq = models.UniqueIndex("(lower(name))", "This technology already exists.")

    name = fields.Char(string="Name", required=True)
    color = fields.Integer(string="Color")

    def _find_or_create(self, names):
        """Technologies for these names, matched case-insensitively; missing ones are created."""
        wanted = {}
        for name in names:
            name = (name or "").strip()
            if name and name.casefold() not in wanted:
                wanted[name.casefold()] = name
        if not wanted:
            return self.browse()
        # A personal list of technologies stays small: comparing in Python avoids =ilike wildcards in names.
        found = {tech.name.casefold(): tech for tech in self.search([])}
        missing = [name for key, name in wanted.items() if key not in found]
        created = self.create([{"name": name} for name in missing]) if missing else self.browse()
        found.update({tech.name.casefold(): tech for tech in created})
        return self.browse([found[key].id for key in wanted])
