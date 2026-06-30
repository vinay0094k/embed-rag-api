"""Tests for documents endpoints."""

import pytest
from io import BytesIO


def test_list_documents(client, auth_headers):
    """Test listing documents."""
    response = client.get(
        "/api/v1/documents?collection_id=default",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert "documents" in data
    assert "total" in data
    assert data["total"] == 0  # Should be empty initially


def test_upload_small_file(client, auth_headers):
    """Test uploading a small file (synchronous)."""
    # Create a small test file
    file_content = b"# Test Document\n\nThis is a test document."

    response = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": auth_headers["Authorization"]},
        files={"file": ("test.md", BytesIO(file_content), "text/markdown")},
        data={"collection_id": "default"}
    )

    # Should succeed (either sync or async response)
    assert response.status_code in [200, 202]
    data = response.json()
    assert "status" in data
    assert "filename" in data


def test_upload_file_without_auth(client):
    """Test that upload requires authentication."""
    file_content = b"Test"

    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("test.md", BytesIO(file_content), "text/markdown")},
        data={"collection_id": "default"}
    )

    assert response.status_code == 401


def test_upload_invalid_file_type(client, auth_headers):
    """Test uploading invalid file type."""
    file_content = b"Invalid content"

    response = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": auth_headers["Authorization"]},
        files={"file": ("test.exe", BytesIO(file_content), "application/octet-stream")},
        data={"collection_id": "default"}
    )

    assert response.status_code == 400
    assert "Invalid file type" in response.json()["detail"]


def test_rate_limiting(client, auth_headers):
    """Test that rate limiting works."""
    # Make many requests quickly
    responses = []
    for i in range(150):  # Exceed the 100 req/min limit for authenticated users
        response = client.get(
            "/api/v1/documents?collection_id=default",
            headers=auth_headers
        )
        responses.append(response.status_code)

    # Eventually should hit rate limit
    assert 429 in responses, "Rate limiting should kick in after many requests"
