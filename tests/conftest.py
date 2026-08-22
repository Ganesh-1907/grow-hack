"""Pytest fixtures for the Flask application."""

from __future__ import annotations

import pytest

from app import app


@pytest.fixture
def client():
    """Return a Flask test client."""
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client
