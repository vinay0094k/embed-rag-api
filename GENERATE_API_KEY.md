# Generate API Key - Usage Guide

Script to easily generate API keys for RAG API users.

## Prerequisites

- Python 3.9+
- Dependencies installed: `pip install -r requirements.txt`
- Database initialized (automatic)

## Usage

### Option 1: Interactive Mode (Easiest)

```bash
cd /home/vinayk/Documents/Daily_Documents/embed-rag-api
python3 generate_api_key.py
```

You'll be prompted for:
- **Username**: Unique identifier for the user
- **Email**: User's email address

Example:
```
Enter username: john
Enter email: john@example.com
```

### Option 2: Command-line Arguments

```bash
python3 generate_api_key.py --username john --email john@example.com
```

**Short form:**
```bash
python3 generate_api_key.py -u john -e john@example.com
```

### Option 3: Using Shell Script

```bash
./generate-key.sh

# Or with arguments
./generate-key.sh --username john --email john@example.com
```

---

## Example Output

```
============================================================
RAG API - Generate API Key
============================================================

Creating user 'john'... ✓
Generating API key... ✓

============================================================
USER CREATED / RETRIEVED
============================================================
User ID:  550e8400-e29b-41d4-a716-446655440000
Username: john
Email:    john@example.com
Active:   True

============================================================
API KEY GENERATED
============================================================
API Key: sk_rag_Km75KU833hMXXYHFcfTbYFqeWWeisGleolCZy6Y99xw

Usage in requests:
Authorization: Bearer sk_rag_Km75KU833hMXXYHFcfTbYFqeWWeisGleolCZy6Y99xw

Example curl:
curl -H "Authorization: Bearer sk_rag_Km75KU833hMXXYHFcfTbYFqeWWeisGleolCZy6Y99xw" \
  http://localhost:8000/api/v1/collections

============================================================
```

---

## Using the Generated API Key

### Test Health Check
```bash
curl http://localhost:8000/health
```

### Create Collection
```bash
API_KEY="sk_rag_Km75KU833hMXXYHFcfTbYFqeWWeisGleolCZy6Y99xw"

curl -X POST http://localhost:8000/api/v1/collections \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "docs", "description": "Documentation"}'
```

### Upload Document
```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -H "Authorization: Bearer $API_KEY" \
  -F "file=@document.md" \
  -F "collection_id=default"
```

### Search
```bash
curl -X POST http://localhost:8000/api/v1/search \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "your search query",
    "collection_id": "default",
    "top_k": 5
  }'
```

---

## Script Features

✅ **Automatic Database Initialization** - Creates SQLite DB if needed  
✅ **User Management** - Creates new users or retrieves existing  
✅ **Secure Key Generation** - Uses `secrets.token_urlsafe()`  
✅ **Key Storage** - Saves API key to database  
✅ **Display Format** - Shows key in ready-to-use format  

---

## Generating Multiple Keys

Each user can have multiple API keys:

```bash
# Create user 'john' first
python3 generate_api_key.py -u john -e john@example.com
# Output: sk_rag_xxxxx (key 1)

# Generate another key for same user
python3 generate_api_key.py -u john -e john@example.com
# Output: sk_rag_yyyyy (key 2)
```

Both keys will work for user 'john'.

---

## Troubleshooting

### Database Error
```
Error: could not locate a Column object...
```
**Solution:** Run script from the project directory
```bash
cd /home/vinayk/Documents/Daily_Documents/embed-rag-api
python3 generate_api_key.py
```

### Module Not Found
```
ModuleNotFoundError: No module named 'app'
```
**Solution:** Install dependencies
```bash
pip install -r requirements.txt
```

### User Already Exists
```
⚠️ User 'john' already exists
```
This is normal - the script will generate a new API key for existing users.

---

## Batch Generation

Create multiple users at once with a script:

```bash
#!/bin/bash

users=(
  "alice:alice@example.com"
  "bob:bob@example.com"
  "charlie:charlie@example.com"
)

for user in "${users[@]}"; do
  username="${user%:*}"
  email="${user#*:}"
  echo "Creating user: $username"
  python3 generate_api_key.py -u "$username" -e "$email"
  echo ""
done
```

Save as `create_users.sh`, then run:
```bash
chmod +x create_users.sh
./create_users.sh
```

---

## Database Location

API keys are stored in:
```
/home/vinayk/Documents/Daily_Documents/embed-rag-api/rag_api.db
```

To view all users and keys (advanced):
```bash
sqlite3 rag_api.db
> SELECT id, username, email FROM users;
> SELECT user_id, key FROM api_keys;
```

---

## Next Steps

1. **Generate API Key** - Use this script
2. **Start RAG API** - `uvicorn main:app --reload`
3. **Use the Key** - Add to request headers
4. **Create Collections** - Organize documents
5. **Upload Documents** - Index files
6. **Search** - Query your knowledge base

---

## Support

For issues or questions:
- Check logs: `tail -f logs/rag_api.log`
- Verify key format: Should start with `sk_rag_`
- Test endpoint: `curl http://localhost:8000/health`
