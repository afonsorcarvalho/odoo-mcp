"""Pytest config. Skips integration tests unless ODOO_TEST_LIVE=1."""
from __future__ import annotations

import os

import pytest


def pytest_collection_modifyitems(config, items):
    if os.environ.get("ODOO_TEST_LIVE") == "1":
        return
    skip_integration = pytest.mark.skip(reason="set ODOO_TEST_LIVE=1 to run")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
