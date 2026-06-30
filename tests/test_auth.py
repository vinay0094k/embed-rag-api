import pytest


def test_user_registration(client):
    """Test user registration with isolated database."""
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "newuser", "email": "new@example.com"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "newuser"
    assert data["email"] == "new@example.com"


def test_user_registration_duplicate(client):
    """Test duplicate user registration fails."""
    # First registration
    client.post(
        "/api/v1/auth/register",
        json={"username": "duplicate", "email": "dup@example.com"}
    )

    # Duplicate should fail
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "duplicate", "email": "dup2@example.com"}
    )
    assert response.status_code == 400


def test_health_check(client):
    """Test health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "v1.0.0"
    assert "request_id" in response.headers


def test_generate_api_key(client, auth_headers):
    """Test API key generation."""
    response = client.post(
        "/api/v1/auth/generate-key",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert "api_key" in data
    assert data["api_key"].startswith("sk_rag_")


def test_request_tracing(client):
    """Test request tracing headers."""
    response = client.get("/health")

    # Check X-Request-ID header is present
    assert "X-Request-ID" in response.headers
    request_id = response.headers["X-Request-ID"]
    assert len(request_id) > 0
