# Testing Guide

## Run Tests

```bash
# Install dependencies
pip install pytest pytest-cov

# Run all tests
pytest tests/

# Run specific test
pytest tests/test_auth.py::test_user_registration

# With coverage report
pytest tests/ --cov=app --cov-report=html

# Verbose output
pytest tests/ -v -s
```

---

## Available Fixtures

### `client`
FastAPI test client with isolated database.
```python
def test_something(client):
    response = client.get("/health")
    assert response.status_code == 200
```

### `auth_headers`
Pre-authenticated headers with API key.
```python
def test_something(client, auth_headers):
    response = client.get("/api/v1/collections", headers=auth_headers)
    assert response.status_code == 200
```

### `test_db`
Fresh in-memory database per test.
```python
def test_something(test_db):
    from app.db.crud import UserCRUD
    user = UserCRUD.create_user(test_db, "user", "user@example.com")
```

---

## Test Examples

### Database Isolation
```python
def test_user_registration(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "john", "email": "john@example.com"}
    )
    assert response.status_code == 200
```

### Authentication
```python
def test_authenticated_request(client, auth_headers):
    response = client.get(
        "/api/v1/collections",
        headers=auth_headers
    )
    assert response.status_code == 200
```

### Error Handling
```python
def test_invalid_email(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "user", "email": "invalid"}
    )
    assert response.status_code == 422
    assert "error" in response.json()
```

---

## Troubleshooting

**Tests interfering with each other:**
```python
# ❌ Wrong
client = TestClient(app)

# ✅ Correct - use fixture
def test_something(client):
    ...
```

**Logs not showing:**
```bash
pytest tests/ -s
```

**Database not isolated:**
Make sure test uses `client` or `test_db` fixture, not custom database.

---

## Key Features

✅ **Structured JSON logging** with request IDs  
✅ **Database isolation** - each test gets fresh DB  
✅ **Request tracing** - track by X-Request-ID  
✅ **Error consistency** - all errors return JSON
