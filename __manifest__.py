{
    "name": "Job Finder",
    "summary": "Foundation for an online portfolio and job search",
    "version": "19.0.1.2.0",
    "category": "Human Resources",
    "depends": ["base", "web", "website"],
    "external_dependencies": {"python": ["pypdf"]},
    "data": [
        "security/ir.model.access.csv",
        "security/job_profile_security.xml",
        "data/website_data.xml",
        "report/job_profile_templates.xml",
        "report/job_profile_report.xml",
        "views/profile_item_views.xml",
        "views/job_profile_views.xml",
        "views/job_profile_menus.xml",
        "views/portfolio_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "job_finder/static/src/scss/portfolio.scss",
        ],
    },
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}
