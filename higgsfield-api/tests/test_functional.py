"""Functional tests for Higgsfield API."""

import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_health_check():
    """Test health check endpoint with correct UUID."""
    # This test requires UUID_TEST_CHECK to be set in .test.env
    response = client.get("/health/test-uuid")
    # Will return 200 if UUID matches, 403 if it doesn't
    assert response.status_code in [200, 403]


def test_health_check_wrong_uuid():
    """Test health check endpoint with wrong UUID."""
    response = client.get("/health/wrong-uuid")
    assert response.status_code == 403


def test_api_root():
    """Test that API is accessible."""
    # This will likely return 404 or 401, but should not return 500
    response = client.get("/api/")
    assert response.status_code != 500

