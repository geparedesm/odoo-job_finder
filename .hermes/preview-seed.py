"""Execute in an isolated Odoo shell with env supplied; synthetic data only."""

from odoo import fields


def seed(env):
    """Create deterministic acceptance scenarios without API keys or external calls."""
    users = env["res.users"]
    for suffix in ("a", "b"):
        login = "job-finder-preview-" + suffix
        user = users.search([("login", "=", login)], limit=1)
        if not user:
            user = users.create({"name": "Synthetic Candidate " + suffix.upper(), "login": login,
                                 "group_ids": [(6, 0, [env.ref("base.group_user").id])]})
        profile = env["job.profile"].search([("user_id", "=", user.id)], limit=1)
        if not profile:
            profile = env["job.profile"].create({"user_id": user.id, "full_name": user.name,
                                                "headline": "Frontend Developer", "location": "Perth"})
        for name in ("Frontend", "Backend", "DevOps", "Engineering & ICT", "Hospitality"):
            if not env["job_finder.cv_area"].search_count([("profile_id", "=", profile.id), ("name", "=", name)]):
                env["job_finder.cv_area"].create({"profile_id": profile.id, "name": name})
        technology = env["job_finder.technology"]._find_or_create(["Preview React"])
        role = env["job_finder.experience"].search([("profile_id", "=", profile.id), ("role", "=", "Synthetic Frontend Developer")], limit=1)
        if not role:
            role = env["job_finder.experience"].create({"profile_id": profile.id, "role": "Synthetic Frontend Developer",
                       "date_start": "2024-01-01", "is_current": True,
                       "cv_area_ids": [(6, 0, profile.cv_area_ids.filtered(lambda area: area.name == "Frontend").ids)]})
            env["job_finder.project"].create({"profile_id": profile.id, "name": "Synthetic frontend project",
                       "experience_id": role.id, "technology_ids": [(6, 0, technology.ids)],
                       "cv_area_ids": [(6, 0, role.cv_area_ids.ids)]})
        searches = env["job_finder.job_search"].with_user(user)
        searches.action_propose_searches()
        search = searches.search([("profile_id", "=", profile.id), ("cv_area_id.name", "=", "Frontend")], limit=1)
        search.write({"is_remote": True, "cities": "Perth,Melbourne"})
        phrases = ["Applicants are not required to hold NV1 clearance", "NV1 clearance is not a requirement",
                   "Previous experience on NV1 projects is desirable", "Must hold NV1 clearance",
                   "Australian citizens, permanent residents or valid visa holders"]
        for index, phrase in enumerate(phrases):
            search._ingest([{"id": f"synthetic-{suffix}-{index}", "title": "Junior Frontend Developer",
                            "description": phrase, "created": fields.Datetime.now().isoformat() + "Z",
                            "location": {"display_name": "Perth"}}])
        scenarios = (
            ("level-required", "Software Engineer — Baseline required", "Baseline required", "Perth"),
            ("obtain-required", "Junior Frontend Developer", "Successful applicant must hold or be able to obtain an NV1 security clearance", "Perth"),
            ("citizenship-required", "Junior Frontend Developer", "Must be an Australian citizen or permanent resident with full working rights", "Perth"),
            ("waived", "Junior Frontend Developer", "NV1 clearance requirement has been waived", "Perth"),
            ("negative-vetting", "Junior Frontend Developer", "Negative vetting required", "Perth"),
            ("no-negative-vetting", "Junior Frontend Developer", "No negative vetting required", "Perth"),
            ("melbourne", "Junior Frontend Developer", "Visa sponsorship available", "Melbourne"),
            ("unconfigured-city", "Junior Frontend Developer", "Synthetic eligible offer", "Darwin"),
        )
        for key, title, snippet, city in scenarios:
            search._ingest([{"id": f"synthetic-{suffix}-{key}", "title": title, "description": snippet,
                            "created": fields.Datetime.now().isoformat() + "Z", "location": {"display_name": city}}])
        for index, state in enumerate(("saved", "applied", "interview", "offer", "rejected", "discarded")):
            key = f"synthetic-{suffix}-state-{index}"
            search._ingest([{"id": key, "title": "Junior Frontend Developer", "description": "Synthetic offer",
                            "created": fields.Datetime.now().isoformat() + "Z", "location": {"display_name": "Perth"}}])
            offer = env["job_finder.job_offer"].search([("profile_id", "=", profile.id), ("adzuna_id", "=", key)])
            offer.write({"state": state, "discard_reason": "Synthetic discard", "rejection_reason": "Synthetic rejection"})
        for key, title in (("senior", "Senior Frontend Developer"), ("threshold", "Unrelated position"), ("evaluated", "Junior Frontend Developer")):
            search._ingest([{"id": f"synthetic-{suffix}-{key}", "title": title, "description": "Synthetic acceptance case",
                            "created": fields.Datetime.now().isoformat() + "Z", "location": {"display_name": "Perth"}}])
        evaluated = env["job_finder.job_offer"].search([("profile_id", "=", profile.id), ("adzuna_id", "=", f"synthetic-{suffix}-evaluated")])
        evaluated.write({"ai_state": "done", "ai_score": 85, "ai_fit": "Synthetic matching example",
                         "ai_gaps": "Synthetic gap", "ai_warnings": "Synthetic data only", "ai_evaluated_at": fields.Datetime.now()})
    login = "job-finder-preview-evaluator"
    if not users.search_count([("login", "=", login)]):
        users.create({"name": "Synthetic evaluator", "login": login,
                      "group_ids": [(6, 0, [env.ref("job_finder.group_job_finder_evaluator").id])]})


if "env" in globals():
    seed(env)  # noqa: F821: provided by the Odoo shell
