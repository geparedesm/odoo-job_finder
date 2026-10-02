"""Tests: standard-library tests (python -m unittest) and Odoo tests (odoo --test-enable)."""

try:
    import odoo  # noqa: F401
except ImportError:  # plain unittest discovers the standard-library tests itself
    pass
else:
    from . import test_odoo_profile  # noqa: F401
