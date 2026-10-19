#!/usr/bin/env python3
"""Preview seed for the job_finder portfolio feature."""

import odoo
from odoo.api import Environment
from odoo.cli import main as odoo_main
from odoo.tools import config


def seed_portfolio_preview(cr, uid, context):
    """
    Idempotent setup for portfolio preview:
    - Activate Spanish language
    - Create/update admin profile with synthetic data
    - Publish the admin profile as portfolio
    - Unpublish any other profiles
    """
    env = Environment(cr, uid, context)

    # Activate Spanish language
    es_lang = env["res.lang"].search([("code", "=", "es_ES")])
    if es_lang and not es_lang.active:
        es_lang.active = True

    # Get the admin user
    admin = env.ref("base.user_admin")

    # Create or update admin's profile with realistic synthetic data
    profile = env["job.profile"].search([("user_id", "=", admin.id)])
    if not profile:
        profile = env["job.profile"].create({"user_id": admin.id})

    profile.write({
        "full_name": "Gabriel Paredes",
        "headline": "Systems Developer & Mechatronics Engineer",
        "location": "San Francisco, CA",
        "email": "gabriel@gp-developer.com",
        "phone": "+00 000 000 000",  # Fake phone to demonstrate it's hidden
        "linkedin": "linkedin.com/in/gabriel-paredes",
        "github": "github.com/geparedesm",
        "website": "gp-developer.com",
        "summary": (
            "I'm a passionate developer bridging hardware and software. "
            "With expertise in both embedded systems and web technologies, "
            "I build solutions that transform ideas into working products. "
            "Currently focused on architecting scalable systems and mentoring teams."
        ),
        "skills": (
            "Embedded Systems\nPython\nJavaScript\nTypeScript\n"
            "React\nDjango\nRust\nArduino\nCircuit Design\n"
            "Web Architecture\nCloud Infrastructure\nPostgreSQL"
        ),
        "projects": (
            "GP-Developer Portfolio\n"
            "Technologies: React, TypeScript, SCSS, Django, Odoo\n"
            "A modern, bilingual portfolio showcasing professional work and capabilities. "
            "Built with responsive design principles and deployed on cloud infrastructure.\n\n"
            "Hardware Automation System\n"
            "Technologies: Python, Arduino, PostgreSQL, REST API\n"
            "Designed and implemented an IoT solution for industrial automation, "
            "resulting in 35% faster processing and real-time monitoring capabilities.\n\n"
            "Full-Stack Web Application\n"
            "Technologies: JavaScript, React, Node.js, Express, MongoDB\n"
            "Developed a collaborative platform for 10,000+ users with real-time features "
            "and comprehensive analytics dashboard."
        ),
        "experience": (
            "Senior Systems Developer\n"
            "Tech Corp, San Francisco | 2022-Present\n"
            "Lead the architecture and development of cloud-based systems handling millions of requests daily. "
            "Mentored a team of 5 engineers and established best practices for code quality and deployment.\n\n"
            "Full-Stack Developer\n"
            "Digital Solutions Inc | 2020-2022\n"
            "Built responsive web applications using React and Django, implemented CI/CD pipelines, "
            "and improved application performance by 40% through optimization efforts.\n\n"
            "Junior Developer\n"
            "StartUp Labs | 2019-2020\n"
            "Contributed to the development of prototype applications and participated in code reviews. "
            "Learned agile methodologies and modern development practices."
        ),
        "education": (
            "Bachelor of Science in Computer Engineering\n"
            "University of California, Berkeley | 2019\n"
            "Specialization in Embedded Systems and Computer Architecture\n\n"
            "Advanced Certification in Full-Stack Web Development\n"
            "Tech Academy | 2020\n"
            "Intensive bootcamp covering modern JavaScript frameworks and backend technologies"
        ),
        "languages": "English - Fluent\nSpanish - Native\nPortuguese - Intermediate",
        "trainings": (
            "AWS Solutions Architect Professional - Amazon Web Services | 2023\n\n"
            "Advanced Python Programming - Real Python | 2022\n\n"
            "Google Cloud Platform Specialization - Coursera | 2021\n\n"
            "React Advanced Patterns - Egghead.io | 2021"
        ),
        "volunteering": (
            "Code Mentor - Tech for Good Foundation | 2022-Present\n"
            "Mentoring underrepresented groups in tech careers and providing guidance on portfolio building.\n\n"
            "Open Source Contributor - Multiple Projects | 2020-Present\n"
            "Active contributor to several open-source projects, improving documentation and fixing bugs.\n\n"
            "Workshop Instructor - Community Tech Center | 2021\n"
            "Taught web development basics to high school students interested in STEM careers."
        ),
        "is_portfolio_published": True,
    })

    # Unpublish any other profiles
    other_profiles = env["job.profile"].search([
        ("is_portfolio_published", "=", True),
        ("id", "!=", profile.id),
    ])
    for other in other_profiles:
        other.is_portfolio_published = False

    env.cr.commit()
    print(f"Portfolio preview seeded: {profile.full_name} is now published")


if __name__ == "__main__":
    # Run via: odoo --no-http --script=/path/to/preview-seed.py
    config.parse_config(["--no-http", "--script", __file__])
    with odoo.api.Environment.manage():
        with odoo.registry(config["db_name"]).cursor() as cr:
            uid = odoo.SUPERUSER_ID
            context = {"lang": "en_US"}
            seed_portfolio_preview(cr, uid, context)
