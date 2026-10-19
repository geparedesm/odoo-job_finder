"""Turn the text of CV sections into structured entries, without Odoo.

Each function takes the text of one section (as stored by `cv_parser.parse_cv_text`) and returns plain
dictionaries that map to the profile models. PDF extraction wraps long lines, so a line that does not start a
new element continues the previous one.
"""

import datetime
import re

_MONTHS = {name: number for number, name in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
_MONTH_YEAR = re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{4})\b", re.IGNORECASE)
_YEAR = re.compile(r"\b(19|20)\d{2}\b")
_PRESENT = re.compile(r"\b(present|current|now)\b", re.IGNORECASE)
_TECH = re.compile(r"^Technologies\s*/\s*methods\s*:\s*", re.IGNORECASE)
_BULLET = re.compile(r"^[•\-*]\s*")
_COURSE_CODE = re.compile(r"^[A-Z]{2,}\d{3,}[A-Z]?$")

EMPLOYMENT_TYPES = {
    "full-time": "full_time", "full time": "full_time",
    "part-time": "part_time", "part time": "part_time",
    "casual": "casual", "shift and event work": "casual",
    "contract": "contract", "freelance": "freelance", "own business": "freelance",
    "internship": "internship",
    "academic collaboration": "academic", "academic project work": "academic",
}
LANGUAGE_LEVELS = {"native": "native", "c2": "c2", "c1": "c1", "b2": "b2", "b1": "b1", "a2": "a2", "a1": "a1"}
TRAINING_STATUSES = {"current": "current", "expired": "expired", "not renewed": "not_renewed"}


def _lines(text):
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def _is_bullet(line):
    return line.startswith("•")


def _is_meta(line):
    return "|" in line


def _join(previous, line):
    """Join a wrapped line, keeping hyphenated words whole ('asynchronous-' + 'operation')."""
    if previous.endswith("-") and not previous.endswith(" -"):
        return previous + line
    return f"{previous} {line}" if previous else line


def parse_period(text):
    """(date_start, date_end, is_current, is_year_only) from 'Dec 2021 - Jan 2025', '2023 - 2024' or 'Feb 2025 - Present'."""
    months = [(int(year), _MONTHS[month[:3].lower()]) for month, year in _MONTH_YEAR.findall(text or "")]
    is_current = bool(_PRESENT.search(text or ""))
    if months:
        start = datetime.date(months[0][0], months[0][1], 1)
        end = datetime.date(months[-1][0], months[-1][1], 1) if len(months) > 1 or not is_current else None
        if is_current:
            end = None
        return start, end, is_current, False
    years = [int(match.group()) for match in _YEAR.finditer(text or "")]
    if years:
        start = datetime.date(years[0], 1, 1)
        end = None if is_current else datetime.date(years[-1], 12, 1)
        return start, end, is_current, True
    return None, None, is_current, False


def _has_period(field):
    return bool(_MONTH_YEAR.search(field) or _YEAR.search(field) or _PRESENT.search(field))


def _parse_meta(fields):
    """Company, location, period, employment type from '|' fields such as 'Duodata | Ecuador | Dec 2021 - Jan 2025 | Full-time'."""
    fields = [field.strip() for field in fields if field.strip()]
    period_index = next((i for i, field in enumerate(fields) if i > 0 and _has_period(field)), None)
    company = fields[0] if fields else ""
    if period_index is None:
        return {"company": company, "location": " | ".join(fields[1:]), "period": "", "type_label": ""}
    return {
        "company": company,
        "location": " | ".join(fields[1:period_index]),
        "period": fields[period_index],
        "type_label": " | ".join(fields[period_index + 1:]),
    }


def _tag(item):
    """A technology tag: trimmed, final period removed, first letter capitalized ('microcontrollers.')."""
    item = item.strip().rstrip(".").strip()
    return item[:1].upper() + item[1:]


def _split_title(name):
    """'Custom ERP modules - Ecuadorian Navy' -> ('Custom ERP modules', 'Ecuadorian Navy')."""
    head, sep, tail = name.rpartition(" - ")
    return (head.strip(), tail.strip()) if sep and head.strip() else (name.strip(), "")


def parse_roles(text, category="work"):
    """Roles with their projects, highlights and description from an Experience or Academic research section.

    A role starts with a title line followed by a '|' line (company, location, dates, type), or with a '|' line
    alone; a second '|' line completes it. A project is a line followed by 'Technologies / methods:'. Bullets
    belong to the current project, or to the role when no project started yet. '(continued)' roles merge into
    the previous role with the same title and company.
    """
    lines = _lines(text)
    roles = []
    role = project = None
    last = None  # what a wrapped line continues: "meta", "tech", "bullet" or None
    awaiting_meta = False

    def set_meta(fields):
        role["meta_fields"] = [field for field in fields]
        role.update(_parse_meta(role["meta_fields"]))

    for i, line in enumerate(lines):
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if _TECH.match(line):
            if project is not None:
                project["technologies"] += _TECH.sub("", line).split(",")
            last = "tech"
        elif _is_bullet(line):
            if role is not None:
                (project["description"] if project is not None else role["highlights"]).append(_BULLET.sub("", line))
            last = "bullet"
        elif _is_meta(line):
            if awaiting_meta:
                set_meta(line.split("|"))
            elif role is not None and last == "meta" and not role["period"]:
                # A second '|' line completes the role ('NIT | Australia' then 'Jul 2024 - Jun 2026 | Academic ...').
                set_meta(role["meta_fields"] + line.split("|"))
            else:
                role = {"title": "", "highlights": [], "description": [], "projects": []}
                roles.append(role)
                project = None
                set_meta(line.split("|"))
            awaiting_meta = False
            last = "meta"
        elif last == "bullet" and role is not None and (line[:1].islower() or line.endswith(".")):
            # A wrapped bullet, even when a new role's '|' line follows it.
            target = project["description"] if project is not None else role["highlights"]
            target[-1] = _join(target[-1], line)
        elif _is_meta(nxt):
            role = {"title": line, "highlights": [], "description": [], "projects": []}
            roles.append(role)
            project = None
            awaiting_meta = True
            last = None
        elif _TECH.match(nxt):
            if role is None:
                role = {"title": "", "highlights": [], "description": [], "projects": []}
                roles.append(role)
                set_meta([])
            name, subtitle = _split_title(line)
            project = {"name": name, "subtitle": subtitle, "technologies": [], "description": []}
            role["projects"].append(project)
            last = None
        elif role is None:
            continue
        elif last == "bullet":
            target = project["description"] if project is not None else role["highlights"]
            target[-1] = _join(target[-1], line)
        elif last == "tech" and project is not None:
            project["technologies"] += line.split(",")
        elif last == "meta":
            # The PDF wrapped the '|' line ('... | Academic' then 'collaboration').
            set_meta(role["meta_fields"][:-1] + [_join(role["meta_fields"][-1].strip(), line)])
        else:
            role["description"].append(line)

    result = []
    for role in roles:
        title = role["title"]
        base_title = re.sub(r"\s*\(continued\)$", "", title, flags=re.IGNORECASE)
        if base_title != title and result and result[-1]["role"] == base_title and result[-1]["company"] == role.get("company"):
            result[-1]["projects"] += _finish_projects(role["projects"], category)
            result[-1]["highlights"] += role["highlights"]
            continue
        date_start, date_end, is_current, year_only = parse_period(role.get("period", ""))
        type_label = role.get("type_label", "")
        result.append({
            "role": base_title or type_label or role.get("company", ""),
            "company": role.get("company", ""),
            "location": role.get("location", ""),
            "date_start": date_start,
            "date_end": date_end,
            "is_current": is_current,
            "is_year_only": year_only,
            "employment_type": EMPLOYMENT_TYPES.get(type_label.casefold()),
            "category": category,
            "description": "\n".join(role["description"]),
            "highlights": role["highlights"],
            "projects": _finish_projects(role["projects"], category),
        })
    return result


def _finish_projects(projects, category):
    return [{
        "name": project["name"],
        "subtitle": project["subtitle"],
        "technologies": [_tag(t) for t in project["technologies"] if _tag(t)],
        "description": "\n".join(project["description"]),
        "category": category,
    } for project in projects]


def parse_skill_groups(text):
    """[{'name', 'technologies'}] from 'Category: item, item' lines; a line without ':' continues the previous one."""
    groups = []
    for line in _lines(text):
        head, sep, rest = line.partition(":")
        if sep and head.strip() and len(head) <= 60:
            groups.append({"name": head.strip(), "items": rest})
        elif groups:
            groups[-1]["items"] = _join(groups[-1]["items"].rstrip(), line)
    return [{
        "name": group["name"],
        "technologies": [_tag(item) for item in group["items"].split(",") if _tag(item)],
    } for group in groups]


def parse_spoken_languages(text):
    """[{'name', 'level'}] from 'Spanish (native), English (B2).'."""
    result = []
    for item in " ".join(_lines(text)).split(","):
        item = item.strip().rstrip(".").strip()
        if not item:
            continue
        match = re.match(r"^(.*?)\s*\(([^)]*)\)$", item)
        name, level = (match.group(1), match.group(2)) if match else (item, "")
        result.append({"name": name.strip(), "level": LANGUAGE_LEVELS.get(level.strip().casefold()[:6].split()[0] if level.strip() else "")})
    return result


def parse_education(text):
    """Qualification line, then a '|' details line: code, institution and location, years, status."""
    result = []
    for line in _lines(text):
        if not _is_meta(line):
            if result and not result[-1]["details_seen"]:
                result[-1]["qualification"] = _join(result[-1]["qualification"], line)
            else:
                result.append({"qualification": line, "details_seen": False, "code": "", "institution": "",
                               "location": "", "year_start": 0, "year_end": 0, "status": False})
            continue
        if not result:
            continue
        entry = result[-1]
        entry["details_seen"] = True
        for field in (f.strip() for f in line.split("|")):
            years = [int(m.group()) for m in _YEAR.finditer(field)]
            lowered = field.casefold()
            if _COURSE_CODE.match(field):
                entry["code"] = field
            elif lowered.startswith(("completed", "graduated", "in progress")):
                entry["status"] = ("graduated" if lowered.startswith("graduated")
                                   else "in_progress" if lowered.startswith("in progress") else "completed")
                if years:
                    entry["year_end"] = years[-1]
            elif years and len(field) <= 20:
                entry["year_start"] = years[0]
                entry["year_end"] = entry["year_end"] or years[-1]
            elif not entry["institution"]:
                institution, sep, place = field.rpartition(", ")
                if sep and place and not re.search(r"\d", place) and len(place.split()) <= 3:
                    entry["institution"], entry["location"] = institution, place
                else:
                    entry["institution"] = field
    for entry in result:
        entry.pop("details_seen")
    return result


def parse_trainings(text):
    """[{'name', 'issuer', 'year', 'status'}] from 'Name | Issuer | Year | Status' lines."""
    result = []
    for line in _lines(text):
        fields = [field.strip() for field in line.split("|")]
        if not _is_meta(line):
            if result:
                result[-1]["name"] = _join(result[-1]["name"], line)
            continue
        entry = {"name": fields[0], "issuer": fields[1] if len(fields) > 1 else "", "year": 0, "status": False}
        for field in fields[2:]:
            years = [int(m.group()) for m in _YEAR.finditer(field)]
            if years and not entry["year"]:
                entry["year"] = years[-1]
            status = TRAINING_STATUSES.get(field.casefold())
            if status:
                entry["status"] = status
        result.append(entry)
    return result


def parse_volunteering(text):
    """Entries: a title line, a '|' line (organisation, location, period), bullets, and 'Roles and recognition' lines."""
    lines = _lines(text)
    result = []
    entry = None
    mode = None  # "bullet" or "recognition"
    for i, line in enumerate(lines):
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if _is_meta(line) and entry is not None and not entry["organisation"]:
            fields = [field.strip() for field in line.split("|")]
            period_index = next((j for j, field in enumerate(fields) if j > 0 and _has_period(field)), len(fields))
            entry["organisation"] = fields[0]
            entry["location"] = " | ".join(fields[1:period_index])
            entry["period"] = " | ".join(fields[period_index:])
            mode = None
            continue
        if _is_meta(nxt) and not _is_bullet(line):
            entry = {"title": line, "organisation": "", "location": "", "period": "", "highlights": [], "recognitions": []}
            result.append(entry)
            mode = None
            continue
        if entry is None:
            continue
        if line.casefold().rstrip(":") == "roles and recognition":
            mode = "recognition"
            continue
        if _is_bullet(line):
            entry["highlights"].append(_BULLET.sub("", line))
            mode = "bullet"
        elif mode == "bullet":
            entry["highlights"][-1] = _join(entry["highlights"][-1], line)
        elif mode == "recognition":
            entry["recognitions"].append(line)
    return result
