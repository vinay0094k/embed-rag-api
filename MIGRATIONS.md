# Database Migrations with Alembic

This project uses **Alembic** for database schema management. Migrations are tracked in version control and applied automatically on startup.

---

## Quick Start

### Automatic (on app startup)
```bash
./run.sh
# Migrations run automatically during init_db()
```

### Manual (if needed)
```bash
source venv/bin/activate
alembic upgrade head        # Apply all pending migrations
alembic downgrade -1        # Rollback last migration
alembic current             # Show current migration
```

---

## Making Schema Changes

### 1. Modify Your Model

Edit `app/db/models.py`:
```python
class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True)
    username = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    phone = Column(String(20), nullable=True)  # ← NEW FIELD
    created_at = Column(DateTime, default=datetime.utcnow)
```

### 2. Generate Migration

```bash
alembic revision --autogenerate -m "Add phone to users"
```

This creates: `alembic/versions/xxx_add_phone_to_users.py`

### 3. Review Migration

Always review the generated migration:
```bash
cat alembic/versions/xxx_add_phone_to_users.py
```

Example output:
```python
def upgrade() -> None:
    op.add_column('users', sa.Column('phone', sa.String(20), nullable=True))

def downgrade() -> None:
    op.drop_column('users', 'phone')
```

### 4. Apply Migration

```bash
alembic upgrade head
```

Or automatically on next app start.

---

## Common Tasks

### Add a New Column
```python
# 1. Update model
user_email = Column(String(255), nullable=False)

# 2. Generate migration
alembic revision --autogenerate -m "Add user email"

# 3. Apply
alembic upgrade head
```

### Rename a Column
```python
# 1. Manual migration (autogenerate can't detect rename)
alembic revision -m "Rename user_email to email"

# 2. Edit alembic/versions/xxx_rename_user_email_to_email.py
def upgrade() -> None:
    op.alter_column('users', 'user_email', new_column_name='email')

def downgrade() -> None:
    op.alter_column('users', 'email', new_column_name='user_email')

# 3. Apply
alembic upgrade head
```

### Drop a Column
```python
# 1. Remove from model
# (delete the Column definition)

# 2. Generate migration
alembic revision --autogenerate -m "Remove unused column"

# 3. Apply
alembic upgrade head
```

### Add an Index
```python
# 1. Update model
__table_args__ = (
    Index('ix_users_email', 'email'),
)

# 2. Generate migration
alembic revision --autogenerate -m "Add email index"

# 3. Apply
alembic upgrade head
```

---

## Checking Migration Status

```bash
# Current migration
alembic current

# History of all migrations
alembic history --verbose

# Pending migrations
alembic upgrade head --sql  # Shows SQL without applying
```

---

## Branching / Merging

If multiple developers create migrations:

```bash
# See all migration heads
alembic heads

# Merge conflicting branches
alembic merge --message="Merge user and order migrations"
```

---

## Production Deployment

### Before Deploying
1. Test migration on staging database
2. Commit migration to git
3. Deploy new code with migration
4. Run migrations: `alembic upgrade head`

### Safe Deployment
```bash
# 1. Deploy new code (with migration file)
git pull origin main

# 2. Run migrations
alembic upgrade head

# 3. Restart app
systemctl restart rag-api
```

### Rollback (if needed)
```bash
# See what version to rollback to
alembic history

# Rollback to previous version
alembic downgrade -1

# Or specific version
alembic downgrade 506e088bc6de
```

---

## Migration File Structure

```
alembic/
├── versions/
│   ├── 506e088bc6de_initial_schema.py
│   ├── a1b2c3d4e5f6_add_phone_to_users.py
│   └── b2c3d4e5f6g7_rename_user_email_to_email.py
├── env.py                 # Alembic environment config
├── script.py.mako         # Migration template
└── README
```

Each migration file has:
```python
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = '506e088bc6de'
branch_labels = None
depends_on = None

def upgrade() -> None:
    """Changes to apply (forward)"""
    op.add_column('users', sa.Column('phone', sa.String(20)))

def downgrade() -> None:
    """Changes to revert (backward)"""
    op.drop_column('users', 'phone')
```

---

## Best Practices

✅ **DO:**
- Commit migrations to git immediately
- Test migrations on staging first
- Review generated migrations carefully
- Keep migrations small and focused
- Use descriptive messages

❌ **DON'T:**
- Edit alembic_version table directly
- Skip migrations in production
- Merge conflicting migrations without review
- Manually run SQL instead of migrations
- Delete migration files

---

## Troubleshooting

### Migration not applying
```bash
# Check current state
alembic current

# See what's pending
alembic upgrade head --sql

# Try upgrading
alembic upgrade head
```

### Conflicting migrations
```bash
# List all heads
alembic heads

# Merge them
alembic merge --message="Merge migrations"
```

### Need to redo a migration
```bash
# Downgrade
alembic downgrade -1

# Fix the migration file
nano alembic/versions/xxx.py

# Re-upgrade
alembic upgrade head
```

### Database locked (SQLite)
```bash
# Close other connections to rag_api.db
lsof | grep rag_api.db

# Delete rag_api.db to start fresh
rm rag_api.db

# Reapply all migrations
alembic upgrade head
```

---

## Schema Versioning

Every deployed schema has a corresponding migration:

```
Production DB Version → Migration Applied → Current State
├─ 506e088bc6de (initial)
├─ a1b2c3d4e5f6 (add phone)
└─ b2c3d4e5f6g7 (rename email)  ← HEAD (current)
```

This ensures:
- ✅ Reproducible deployments
- ✅ Safe rollbacks
- ✅ Clear change history
- ✅ Team coordination

---

## Resources

- [Alembic Docs](https://alembic.sqlalchemy.org/)
- [SQLAlchemy Types](https://docs.sqlalchemy.org/en/20/core/types.html)
- [Migration Operations](https://alembic.sqlalchemy.org/en/latest/ops.html)
