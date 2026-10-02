{
    "name": "Job Finder",
    "summary": "Foundation for an online portfolio and job search",
    "version": "19.0.1.0.0",
    "category": "Human Resources",
    "depends": ["base"],
    "external_dependencies": {"python": ["pypdf"]},
    "data": [
        "security/ir.model.access.csv",
        "security/job_profile_security.xml",
        "views/job_profile_views.xml",
        "views/job_profile_menus.xml",
    ],
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}
