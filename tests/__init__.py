"""Tests: standard-library tests (python -m unittest) and Odoo tests (odoo --test-enable)."""

try:
    import odoo  # noqa: F401
except ImportError:  # plain unittest discovers the standard-library tests itself
    pass
else:
    from . import test_case_study_page  # noqa: F401
    from . import test_cv_areas  # noqa: F401
    from . import test_job_profile_report  # noqa: F401
    from . import test_odoo_profile  # noqa: F401
    from . import test_portfolio_content  # noqa: F401
    from . import test_portfolio_case_study  # noqa: F401
    from . import test_portfolio_page  # noqa: F401
    from . import test_portfolio_profile  # noqa: F401
    from . import test_profile_form  # noqa: F401
    from . import test_structured_profile  # noqa: F401
