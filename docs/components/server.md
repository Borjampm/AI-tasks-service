# Server Module

The async gRPC server that handles chat requests with session persistence, structured logging, and graceful shutdown.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Incoming gRPC Request                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    LoggingInterceptor                       │
│  • Captures request timing                                  │
│  • Logs method, status (OK/ERROR), elapsed time            │
│  • Outputs Cloud Logging-compatible JSON                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   ChatServiceServicer                       │
│  • Manages session IDs for conversation continuity         │
│  • Streams AI responses in real-time                       │
│  • Updates message history after each exchange             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      SessionStore                           │
│  • In-memory session storage with TTL expiration           │
│  • Background cleanup task for expired sessions            │
│  • LRU eviction when capacity limit reached                │
└─────────────────────────────────────────────────────────────┘
```

## Components

### ChatServiceServicer (`main.py`)

Handles streaming chat requests with session-based message history.

```python
# Automatic session creation
session_id = session_store.create_session_id()

# Message history retrieval
history = await session_store.get_history(session_id)

# Streaming response with real-time chunks
async with chat_agent.run_stream(message, message_history=history) as result:
    async for text in result.stream_text(delta=True):
        yield ChatResponse(message=text, session_id=session_id)
```

**Capabilities:**
- Creates new sessions when client doesn't provide a session ID
- Retrieves and passes message history to AI agent
- Streams response chunks as they're generated
- Updates session history after successful completion
- Sets INTERNAL status code on errors

### SessionStore (`sessions.py`)

Thread-safe in-memory store for managing AI conversation sessions.

```python
from sessions import session_store

# Start background cleanup (call on server startup)
await session_store.start_cleanup_task()

# Create new session
session_id = session_store.create_session_id()

# Retrieve history (updates last_accessed timestamp)
history = await session_store.get_history(session_id)

# Update history (trims to MAX_HISTORY_MESSAGES)
await session_store.update_history(session_id, new_messages)

# Stop cleanup (call on server shutdown)
await session_store.stop_cleanup_task()
```

**Key Features:**
- TTL-based expiration (default: 60 minutes)
- Background cleanup every 5 minutes
- Maximum 10,000 concurrent sessions (LRU eviction)
- Maximum 100 messages per session (keeps most recent)
- UUID v4 validation for session IDs

**Configuration Constants:**
| Constant | Default | Purpose |
|----------|---------|---------|
| `CLEANUP_INTERVAL_SECONDS` | 300 | How often cleanup runs |
| `MAX_SESSIONS` | 10000 | Capacity before eviction |
| `MAX_HISTORY_MESSAGES` | 100 | Message limit per session |

### LoggingInterceptor (`logging_interceptor.py`)

gRPC async server interceptor for Cloud Logging-compatible request logging.

```python
from logging_interceptor import setup_logging, LoggingInterceptor

# Configure logging at startup
setup_logging()

# Add interceptor to server
server = aio.server(interceptors=[LoggingInterceptor()])
```

**Log Output Format (JSON):**
```json
{
  "severity": "INFO",
  "message": "/chat.ChatService/Chat OK 234.5ms",
  "grpc_method": "/chat.ChatService/Chat",
  "elapsed_ms": 234.5
}
```

**Capabilities:**
- Logs method name, status, and timing for every RPC
- Wraps both unary and streaming handlers
- Outputs structured JSON for Cloud Logging
- Captures exceptions with stack traces

## Server Lifecycle

### Startup Sequence
1. Configure Cloud Logging JSON formatter
2. Initialize Logfire instrumentation
3. Start session cleanup background task
4. Create gRPC server with logging interceptor
5. Register ChatService and Health services
6. Bind to configured port
7. Set up SIGTERM/SIGINT handlers

### Graceful Shutdown
1. Set health status to NOT_SERVING
2. Stop session cleanup task
3. Wait up to 30 seconds for in-flight RPCs
4. Close server

## Usage

```python
import asyncio
from main import serve

asyncio.run(serve())
```

Or via command line:
```bash
cd server && uv run main.py
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PORT` | No | 50051 | Server listen port |
| `GOOGLE_API_KEY` | Yes | - | API key for AI agent |
| `DATABASE_URL` | No | - | For database-backed features |

## Health Checks

The server exposes the standard gRPC health check protocol:

```bash
grpc_health_probe -addr=localhost:50051
```

Health status transitions:
- `SERVING` on startup
- `NOT_SERVING` during graceful shutdown

## See Also

- [AI Agents](agents.md) - Chat agent configuration
- [Database Module](database.md) - Database access for AI agents
- [Getting Started](../guides/getting-started.md) - Local development setup
