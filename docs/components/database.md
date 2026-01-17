# Database Module

A secure, read-only database abstraction layer for Supabase PostgreSQL access, designed for AI agents that need to query user data safely.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     AI Agent / Application                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      QueryExecutor                           │
│  • Validates queries (read-only enforcement)                 │
│  • Executes with retries and exponential backoff            │
│  • Formats results for AI consumption                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    DatabaseManager                           │
│  • Singleton connection pool                                 │
│  • Supabase pooler compatibility (statement_cache_size=0)   │
│  • Health monitoring via pool_status                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Supabase PostgreSQL (via pooler)               │
│              postgresql://...@pooler.supabase.com:6543      │
└─────────────────────────────────────────────────────────────┘
```

## Components

### DatabaseManager (`manager.py`)

Singleton connection pool manager with Supabase compatibility.

```python
from database import DatabaseManager

# Get singleton instance (creates pool on first call)
db = await DatabaseManager.get_instance()

# Use connection
async with db.connection() as conn:
    rows = await conn.fetch("SELECT * FROM users")

# Check pool health
print(db.pool_status)
# {'status': 'initialized', 'size': 5, 'idle_size': 3, 'min_size': 1, 'max_size': 10}

# Cleanup (call on shutdown)
await db.close()

# Reset singleton (for testing)
await DatabaseManager.reset_instance()
```

**Key Features:**
- Singleton pattern ensures one pool per application
- `statement_cache_size=0` for Supabase pooler (pgbouncer) compatibility
- Async context manager for safe connection handling
- Pool metrics for health monitoring

### QueryValidator (`query.py`)

Validates SQL queries for safety before execution.

```python
from database import QueryValidator, QueryValidationError

# Valid queries
QueryValidator.validate("SELECT * FROM users")
QueryValidator.validate("WITH cte AS (SELECT 1) SELECT * FROM cte")
QueryValidator.validate("EXPLAIN SELECT * FROM users")

# Rejected queries (raises QueryValidationError)
QueryValidator.validate("DELETE FROM users")  # Forbidden keyword
QueryValidator.validate("INSERT INTO users VALUES (1)")  # Not SELECT

# Multi-tenant isolation: require user_id filter
QueryValidator.validate(
    "SELECT * FROM transactions WHERE user_id = '123'",
    user_id="123"
)  # Passes

QueryValidator.validate(
    "SELECT * FROM transactions",
    user_id="123"
)  # Raises: must include user_id filter
```

**Forbidden Keywords:** INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, GRANT, REVOKE, VACUUM, ANALYZE

**Allowed Prefixes:** SELECT, WITH, EXPLAIN

### QueryExecutor (`query.py`)

Executes validated queries with retries and result formatting.

```python
from database import DatabaseManager, QueryExecutor

db = await DatabaseManager.get_instance()
executor = QueryExecutor(db, max_rows=100, max_retries=3)

# Execute and get structured result
result = await executor.execute(
    "SELECT * FROM transactions WHERE user_id = '123'",
    user_id="123"
)
print(result.rows)       # List of dicts
print(result.row_count)  # Total rows (before truncation)
print(result.columns)    # Column names
print(result.truncated)  # True if exceeded max_rows

# Execute and get formatted string (for AI agents)
formatted = await executor.execute_formatted(
    "SELECT name, amount FROM transactions WHERE user_id = '123'",
    user_id="123"
)
print(formatted)
# name | amount
# ---------------
# Groceries | 50.00
# Rent | 1200.00
```

**Key Features:**
- EXPLAIN validation before execution (catches syntax errors early)
- Exponential backoff retries on transient failures
- Result truncation to prevent large responses
- Exception chaining preserves original errors

### SchemaDiscovery (`schema.py`)

Dynamic schema introspection with caching.

```python
from database import DatabaseManager, SchemaDiscovery

db = await DatabaseManager.get_instance()
schema = SchemaDiscovery(db)

# Load schema from database
await schema.refresh()

# List tables
tables = schema.get_tables()
# ['hobby_categories', 'transactions', 'user_accounts', ...]

# Get table details
table = schema.get_table("transactions")
print(table.name)         # 'transactions'
print(table.column_names) # ['id', 'amount', 'user_id', ...]

for col in table.columns:
    print(f"{col.name}: {col.data_type} ({'NULL' if col.is_nullable else 'NOT NULL'})")

# Build context for AI agent system prompt
context = schema.build_context_for_agent()
# Returns formatted markdown with all tables and columns

# Build context for single table
table_context = schema.build_table_context("transactions")
```

**Key Features:**
- On-demand refresh via `refresh()` method
- Caches schema to avoid repeated introspection
- Generates AI-friendly context strings
- Includes column comments when available

## Error Handling

```python
from database import (
    QueryValidationError,  # Invalid query (forbidden keyword, missing user_id)
    QueryExecutionError,   # Execution failed (syntax error, connection issues)
)

try:
    result = await executor.execute("SELECT * FROM users", user_id="123")
except QueryValidationError as e:
    print(f"Validation failed: {e}")
except QueryExecutionError as e:
    print(f"Execution failed: {e}")
    print(f"Original error: {e.original_error}")  # Access underlying exception
    print(f"Cause chain: {e.__cause__}")          # Standard Python exception chaining
```

## Full Example

```python
import asyncio
from database import DatabaseManager, QueryExecutor, SchemaDiscovery

async def main():
    # Initialize
    db = await DatabaseManager.get_instance()
    executor = QueryExecutor(db)
    schema = SchemaDiscovery(db)

    # Load schema
    await schema.refresh()
    print(f"Available tables: {schema.get_tables()}")

    # Execute query with user isolation
    user_id = "50a3e741-3839-4e8c-9ba6-41ae5a218646"
    result = await executor.execute_formatted(
        f"SELECT title, amount FROM transactions WHERE user_id = '{user_id}' LIMIT 5",
        user_id=user_id
    )
    print(result)

    # Cleanup
    await db.close()

asyncio.run(main())
```

## Testing

```bash
# Run all database tests (80 tests)
uv run pytest tests/ -v

# Run specific test files
uv run pytest tests/test_query_validator.py -v
uv run pytest tests/test_query_executor.py -v
uv run pytest tests/test_database_manager.py -v
uv run pytest tests/test_schema_discovery.py -v

# Run manual integration test
uv run python scripts/test_database.py
```

## Configuration

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | Supabase PostgreSQL connection string | `postgresql://user.project-ref:password@pooler.supabase.com:6543/postgres` |

### Pool Settings

```python
db = await DatabaseManager.get_instance(
    database_url="postgresql://...",  # Or use DATABASE_URL env var
    min_size=1,                       # Minimum connections
    max_size=10,                      # Maximum connections
)
```

### Query Executor Settings

```python
executor = QueryExecutor(
    db_manager=db,
    max_rows=100,     # Truncate results beyond this
    max_retries=3,    # Retry transient failures
)
```

## Security

1. **Read-only enforcement**: Only SELECT, WITH, and EXPLAIN queries allowed
2. **Forbidden keywords**: INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, GRANT, REVOKE blocked
3. **Multi-tenant isolation**: Optional user_id filter requirement
4. **EXPLAIN validation**: Queries validated before execution
5. **Read-only database user**: Use a PostgreSQL role with only SELECT permissions

### Creating a Read-Only User (Supabase)

```sql
-- In Supabase SQL Editor
CREATE ROLE readonly_agent WITH LOGIN PASSWORD 'secure_password';
GRANT CONNECT ON DATABASE postgres TO readonly_agent;
GRANT USAGE ON SCHEMA public TO readonly_agent;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly_agent;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO readonly_agent;
```

Then use connection string:
```
postgresql://readonly_agent.project-ref:secure_password@pooler.supabase.com:6543/postgres
```
