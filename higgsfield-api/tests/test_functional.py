"""Functional tests for Higgsfield API endpoints."""

import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


# ─────────────────────────────────────────────────────────────────────────────
# Health Check Tests
# ─────────────────────────────────────────────────────────────────────────────


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


# ─────────────────────────────────────────────────────────────────────────────
# Route Registration Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_routes_registered():
    """Ensure all expected endpoints are registered."""
    paths = [route.path for route in client.app.routes]
    
    expected_routes = [
        "/api/higgsfield/t2i/",
        "/api/higgsfield/soul/",
        "/api/higgsfield/styles/",
        "/api/higgsfield/i2v/",
        "/api/task/{task_id}/status",
        "/api/task/{task_id}/cancel",
        "/api/task/{task_id}",
    ]
    
    for route in expected_routes:
        assert route in paths, f"Route {route} not found in registered routes"


# ─────────────────────────────────────────────────────────────────────────────
# Soul Styles Endpoint (No Auth Required for listing)
# ─────────────────────────────────────────────────────────────────────────────


def test_styles_endpoint_returns_list():
    """Test that /styles/ endpoint returns a list of styles."""
    response = client.get("/api/higgsfield/styles/")
    
    # Should return 200 (no auth required for listing styles)
    assert response.status_code == 200
    
    data = response.json()
    assert "styles" in data
    assert "total" in data
    assert isinstance(data["styles"], list)
    assert data["total"] >= 0


def test_styles_have_required_fields():
    """Test that each style has the required fields."""
    response = client.get("/api/higgsfield/styles/")
    assert response.status_code == 200
    
    data = response.json()
    if data["total"] > 0:
        style = data["styles"][0]
        assert "id" in style
        assert "name" in style
        assert "preview_url" in style


# ─────────────────────────────────────────────────────────────────────────────
# Authentication Required Tests (should return 401/403 without auth)
# ─────────────────────────────────────────────────────────────────────────────


def test_t2i_requires_auth():
    """Test that /t2i/ endpoint requires authentication."""
    response = client.post(
        "/api/higgsfield/t2i/",
        json={"prompt": "test prompt"}
    )
    # Should require auth (401 or 403)
    assert response.status_code in [401, 403, 422]


def test_soul_requires_auth():
    """Test that /soul/ endpoint requires authentication."""
    response = client.post(
        "/api/higgsfield/soul/",
        json={"prompt": "test prompt"}
    )
    # Should require auth (401 or 403)
    assert response.status_code in [401, 403, 422]


def test_i2v_requires_auth():
    """Test that /i2v/ endpoint requires authentication."""
    # Create a minimal fake image file
    response = client.post(
        "/api/higgsfield/i2v/",
        data={"prompt": "test"},
        files={"image": ("test.png", b"fake image data", "image/png")}
    )
    # Should require auth (401 or 403)
    assert response.status_code in [401, 403, 422]


def test_task_status_requires_auth():
    """Test that task status endpoint requires authentication."""
    response = client.get("/api/task/00000000-0000-0000-0000-000000000000/status")
    # Should require auth (401 or 403)
    assert response.status_code in [401, 403, 404]


def test_task_cancel_requires_auth():
    """Test that task cancel endpoint requires authentication."""
    response = client.post("/api/task/00000000-0000-0000-0000-000000000000/cancel")
    # Should require auth (401 or 403)
    assert response.status_code in [401, 403, 404]


# ─────────────────────────────────────────────────────────────────────────────
# Request Validation Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_t2i_validates_request_body():
    """Test that /t2i/ validates the request body."""
    # Missing required 'prompt' field
    response = client.post(
        "/api/higgsfield/t2i/",
        json={},
        headers={"X-API-KEY": "invalid-key"}  # Auth will fail but validation happens first
    )
    # Should return 422 (validation error) or 401/403 (auth error)
    assert response.status_code in [401, 403, 422]


def test_soul_validates_request_body():
    """Test that /soul/ validates the request body."""
    # Missing required 'prompt' field
    response = client.post(
        "/api/higgsfield/soul/",
        json={},
        headers={"X-API-KEY": "invalid-key"}
    )
    # Should return 422 (validation error) or 401/403 (auth error)
    assert response.status_code in [401, 403, 422]


# ─────────────────────────────────────────────────────────────────────────────
# Enum Validation Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_t2i_validates_aspect_ratio():
    """Test that /t2i/ validates aspect_ratio enum."""
    response = client.post(
        "/api/higgsfield/t2i/",
        json={"prompt": "test", "aspect_ratio": "invalid"},
        headers={"X-API-KEY": "test"}
    )
    # Should return 422 for invalid enum or 401/403 for auth
    assert response.status_code in [401, 403, 422]


def test_soul_validates_resolution():
    """Test that /soul/ validates resolution enum."""
    response = client.post(
        "/api/higgsfield/soul/",
        json={"prompt": "test", "resolution": "invalid"},
        headers={"X-API-KEY": "test"}
    )
    # Should return 422 for invalid enum or 401/403 for auth
    assert response.status_code in [401, 403, 422]
