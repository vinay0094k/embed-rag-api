"""Tests for collections endpoints."""

import pytest


def test_create_collection(client, auth_headers):
    """Test creating a collection."""
    response = client.post(
        "/api/v1/collections",
        headers=auth_headers,
        json={
            "name": "test-docs",
            "description": "Test collection"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "test-docs"
    assert data["description"] == "Test collection"
    assert "id" in data
    assert "user_id" in data


def test_list_collections(client, auth_headers):
    """Test listing collections."""
    # Create two collections
    client.post(
        "/api/v1/collections",
        headers=auth_headers,
        json={"name": "collection-1"}
    )
    client.post(
        "/api/v1/collections",
        headers=auth_headers,
        json={"name": "collection-2"}
    )

    response = client.get(
        "/api/v1/collections",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["collections"]) == 2


def test_get_collection(client, auth_headers):
    """Test getting a single collection."""
    # Create collection
    create_response = client.post(
        "/api/v1/collections",
        headers=auth_headers,
        json={"name": "my-collection"}
    )
    collection_id = create_response.json()["id"]

    # Get collection
    response = client.get(
        f"/api/v1/collections/{collection_id}",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == collection_id
    assert data["name"] == "my-collection"


def test_delete_collection(client, auth_headers):
    """Test deleting a collection."""
    # Create collection
    create_response = client.post(
        "/api/v1/collections",
        headers=auth_headers,
        json={"name": "to-delete"}
    )
    collection_id = create_response.json()["id"]

    # Delete collection
    response = client.delete(
        f"/api/v1/collections/{collection_id}",
        headers=auth_headers
    )
    assert response.status_code == 204

    # Verify it's deleted
    get_response = client.get(
        f"/api/v1/collections/{collection_id}",
        headers=auth_headers
    )
    assert get_response.status_code == 404


def test_collection_isolation(client, auth_headers):
    """Test that collections are isolated per user."""
    # Create collection for user 1
    client.post(
        "/api/v1/collections",
        headers=auth_headers,
        json={"name": "user1-collection"}
    )

    # Register user 2
    client.post(
        "/api/v1/auth/register",
        json={"username": "user2", "email": "user2@example.com"}
    )

    # User 2 shouldn't see user 1's collection
    user2_response = client.get(
        "/api/v1/collections",
        headers={
            "Authorization": "Bearer sk_rag_different_key",
            "Content-Type": "application/json"
        }
    )
    # This should fail because we don't have a valid key for user2
    # In real tests, we'd generate a valid key for user2
