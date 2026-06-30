# Testing Guide

## **Overview**

The RAG API now includes:
- ✅ **Structured JSON logging** with request IDs
- ✅ **Global exception handler** for consistent error responses
- ✅ **Database test isolation** (each test gets its own DB)
- ✅ **Request tracing** across all logs

---

## **Running Tests**

### **Install Test Dependencies**

```bash
pip install pytest pytest-cov
```

### **Run All Tests**

```bash
pytest tests/
```

### **Run Specific Test**

```bash
pytest tests/test_auth.py::test_user_registration
```

### **Run with Coverage**

```bash
pytest tests/ --cov=app --cov-report=html
```

### **Run Tests Verbosely**

```bash
pytest tests/ -v -s
```

---

## **Features**

### **1. Structured JSON Logging**

Every log entry is structured JSON with request ID:

```json
{
  "timestamp": "2026-06-28T13:00:00.123456",
  "level": "INFO",
  "logger": "app.api.v1.endpoints.auth",
  "message": "→ POST /api/v1/auth/register",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "endpoint": "/api/v1/auth/register",
  "method": "POST",
  "client": "127.0.0.1"
}
```

**Benefits:**
- Easy to parse with log aggregators (ELK, Datadog, etc.)
- Request ID for tracing across services
- Full context in each log entry

### **2. Global Exception Handler**

All exceptions return consistent JSON responses:

**Example - Validation Error (422):**
```json
{
  "error": {
    "type": "ValidationError",
    "message": "Request validation failed",
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "details": {
      "errors": [
        {
          "field": "email",
          "message": "invalid email format",
          "type": "value_error.email"
        }
      ]
    }
  }
}
```

**Example - Database Error (500):**
```json
{
  "error": {
    "type": "DatabaseError",
    "message": "Database operation failed",
    "request_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

**Example - RAG Error (400):**
```json
{
  "error": {
    "type": "RAGException",
    "message": "Document not found",
    "request_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

**Benefits:**
- Clients know what went wrong
- Request ID for support/debugging
- No raw Python tracebacks exposed

### **3. Database Test Isolation**

Each test gets an isolated in-memory SQLite database:

```python
def test_user_registration(client, test_db):
    """test_db is fresh for each test"""
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "user1", "email": "user1@example.com"}
    )
    assert response.status_code == 200
    # Database is cleaned up after test


def test_another_test(client, test_db):
    """test_db is fresh again - no data from previous test"""
    # Can safely use same username as previous test
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "user1", "email": "user1@example.com"}
    )
    assert response.status_code == 200
```

**Benefits:**
- Tests don't interfere with each other
- No need to clean up data between tests
- Fast (in-memory database)
- Can run tests in parallel safely

### **4. Request Tracing**

Every request gets a unique ID for end-to-end tracing:

```bash
# Request comes in with auto-generated ID
curl http://localhost:8000/api/v1/health

# Response includes X-Request-ID header
# X-Request-ID: 550e8400-e29b-41d4-a716-446655440000

# All logs for this request share the same ID
# → GET /api/v1/health [request_id: 550e8400...]
# Generating API Key... [request_id: 550e8400...]
# ← GET /api/v1/health 200 [request_id: 550e8400...]
```

**Benefits:**
- Trace requests across all services
- Link all related logs together
- Debug issues by request ID
- Monitor request latency

---

## **Test Examples**

### **Test with Database Isolation**

```python
def test_user_isolation(client, test_db):
    """Each test has isolated database."""
    # Create user in test 1
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "john", "email": "john@example.com"}
    )
    assert response.status_code == 200

    # Next test won't see this user
```

### **Test with Authentication**

```python
def test_authenticated_request(client, auth_headers):
    """Use pre-authenticated headers."""
    response = client.get(
        "/api/v1/collections",
        headers=auth_headers
    )
    assert response.status_code == 200
```

### **Test Error Handling**

```python
def test_invalid_input(client):
    """Test structured error response."""
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "user", "email": "invalid-email"}  # Invalid email
    )
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert "request_id" in data["error"]
```

### **Test Query Expansion**

```python
def test_search_with_query_expansion(client, auth_headers):
    """Test query expansion for improved relevance."""
    # First, upload a document
    # Then search with expansion enabled
    response = client.post(
        "/api/v1/search",
        headers=auth_headers,
        json={
            "query": "kubernetes deployment",
            "collection_id": "default",
            "top_k": 5,
            "use_query_expansion": True  # Enable expansion
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert "search_time_ms" in data  # Will be longer due to expansion
    assert data["search_time_ms"] > 1000  # Typical expansion overhead
    
    # Results should have improved relevance scores
    if data["results"]:
        assert all(r["score"] > 0 for r in data["results"])
```

---

## **Logging in Tests**

Tests automatically capture logs:

```bash
# Run with log output
pytest tests/ -v -s

# Or save logs to file
pytest tests/ -v -s > test_output.log
```

**Log output includes:**
- Request tracing
- Exception details
- Timing information
- Request IDs for debugging

---

## **Fixtures Available**

### **`test_db`**
Fresh in-memory database for each test.

```python
def test_something(test_db):
    # test_db is a SQLAlchemy session
    from app.db.crud import UserCRUD
    user = UserCRUD.create_user(test_db, "user", "user@example.com")
```

### **`client`**
FastAPI test client with isolated database.

```python
def test_something(client):
    response = client.get("/health")
    assert response.status_code == 200
```

### **`auth_headers`**
Pre-authenticated headers with generated API key.

```python
def test_something(client, auth_headers):
    response = client.get(
        "/api/v1/collections",
        headers=auth_headers
    )
    assert response.status_code == 200
```

---

## **CI/CD Integration**

### **GitHub Actions Example**

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt pytest
      - run: pytest tests/ --cov=app
```

---

## **Troubleshooting**

### **Tests Interfering with Each Other**

Ensure you're using the `client` fixture (not creating your own):

```python
# ❌ Wrong - shares global database
from fastapi.testclient import TestClient
from main import app
client = TestClient(app)

# ✅ Correct - gets isolated database
def test_something(client):
    ...
```

### **Logs Not Showing**

Run with `-s` flag:

```bash
pytest tests/ -s
```

### **Database Not Isolated**

Make sure test is using `test_db` fixture:

```python
# ✅ Correct
def test_something(client, test_db):
    ...

# ❌ Wrong - won't get isolation
def test_something():
    ...
```

---

## **Best Practices**

1. **Use fixtures** - Always use `client` and `auth_headers` fixtures
2. **Test isolation** - Each test is independent
3. **Check request_id** - Verify X-Request-ID in responses
4. **Test errors** - Verify error response format
5. **Use fixtures** - Don't create your own test client

---

## **Next Steps**

```bash
# 1. Run tests
pytest tests/ -v

# 2. Check coverage
pytest tests/ --cov=app --cov-report=html

# 3. View coverage report
open htmlcov/index.html

# 4. Add more tests for your endpoints
cp tests/test_auth.py tests/test_documents.py
```
