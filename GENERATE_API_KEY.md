# Generate API Key

Script to generate API keys for users.

## Usage

**Interactive mode:**
```bash
python3 generate_api_key.py
```

You'll be prompted for username and email.

**With arguments:**
```bash
python3 generate_api_key.py -u john -e john@example.com
```

---

## Example Output

```
API Key: sk_rag_Km75KU833hMXXYHFcfTbYFqeWWeisGleolCZy6Y99xw

Usage in requests:
Authorization: Bearer sk_rag_Km75KU833hMXXYHFcfTbYFqeWWeisGleolCZy6Y99xw
```

---

## Using the API Key

```bash
# Test health
curl http://localhost:8000/health

# Create collection
API_KEY="sk_rag_xxxxx"
curl -X POST http://localhost:8000/api/v1/collections \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "docs", "description": "Documentation"}'

# Search
curl -X POST http://localhost:8000/api/v1/search \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "search term", "collection_id": "default", "top_k": 5}'
```

---

## Multiple Keys

Each user can have multiple keys:

```bash
# Generate key 1
python3 generate_api_key.py -u john -e john@example.com
# Output: sk_rag_xxxxx

# Generate key 2 for same user
python3 generate_api_key.py -u john -e john@example.com
# Output: sk_rag_yyyyy
```

Both keys work for user 'john'.

---

## Troubleshooting

**Module not found:**
```bash
pip install -r requirements.txt
```

**Database error:**
```bash
cd embed-rag-api
python3 generate_api_key.py
```

**User already exists:**
Normal behavior - generates new key for existing user.
