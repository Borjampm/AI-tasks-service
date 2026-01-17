# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Rules

- When discussing important project details with the user, update this file with relevant information that would help future sessions.
- Run tests before and after making changes to code to review if anything was broken.
- Do not write tests or documentation.
- Never run production commands.
- Search the README.md for relevant documentation.

## Project Overview

A gRPC-based AI service using Pydantic AI with Google's Gemma model. Browser connectivity is handled via an Envoy proxy that translates gRPC-Web (HTTP/1.1) to gRPC (HTTP/2).

**Architecture:** `Browser (gRPC-Web) → Envoy Proxy (:8080) → gRPC Server (:50051)`

## Common Commands

### Run the gRPC Server
```bash
cd server && uv run main.py
```

### Run the Python Client
```bash
cd client && uv run main.py
```

### Start Envoy Proxy (Local Development)
```bash
docker run -p 8080:8080 \
  -v $(pwd)/envoy/envoy.local.yaml:/etc/envoy/envoy.yaml \
  envoyproxy/envoy:v1.28-latest
```

### Generate Protocol Buffers

**Server (Python):**
```bash
uv run python -m grpc_tools.protoc -I protobufs --python_out=server --pyi_out=server --grpc_python_out=server ai_service.proto
```

**Client (Python):**
```bash
uv run python -m grpc_tools.protoc -I protobufs --python_out=client --pyi_out=client --grpc_python_out=client ai_service.proto
```

### Run Tests
```bash
uv run pytest
```

### Build Docker Image
```bash
docker build -t ai-tasks-service .
```

## Code Architecture

### Server (`server/`)
- `main.py` - Async gRPC server using `grpc.aio`. Exposes `AIServiceServicer` with streaming `QA` method. Includes health checks and graceful shutdown handling.
- `agents/` - Pydantic AI agents. `chat.py` defines `chat_agent` using Google's Gemma model. `database.py` is a text-to-SQL agent (being refactored).
- `database/` - Database abstraction layer:
  - `manager.py` - `DatabaseManager` singleton for connection pooling (Supabase-compatible)
  - `query.py` - `QueryValidator` (read-only enforcement) and `QueryExecutor` (safe query execution)
  - `schema.py` - `SchemaDiscovery` for dynamic schema introspection with caching
- `logging_interceptor.py` - gRPC interceptor for Cloud Logging-compatible JSON logs.
- `ai_service_pb2.py`, `ai_service_pb2_grpc.py` - Generated protobuf code (regenerate after modifying `.proto` files).

### Client (`client/`)
- `main.py` - CLI client for testing. Uses SSL for remote connections, insecure for localhost.

### Protobufs (`protobufs/`)
- `ai_service.proto` - Service definition with `QA` streaming RPC.

### Envoy (`envoy/`)
- `envoy.local.yaml` - Local development config (connects to `host.docker.internal:50051`).
- `envoy.template.yaml` - Production template with environment variable substitution.

## Environment Variables

- `GOOGLE_API_KEY` - Required for the AI agent.
- `PORT` - gRPC server port (default: 50051).
- `SERVICE_URL` - Client target URL (default: localhost:50051).
- `DATABASE_URL` - Supabase PostgreSQL connection string (pooler format: `postgresql://user.project-ref:password@pooler.supabase.com:6543/postgres`).

## Database Connection (Supabase)

Uses direct PostgreSQL via `asyncpg` with a read-only user for security. Connection goes through Supabase's connection pooler (port 6543).

**Documentation**: See `docs/components/database.md` for detailed documentation on the database module (DatabaseManager, QueryExecutor, SchemaDiscovery).

## Production Deployment (Cloud Run)

You will never deploy. Always propose how to deploy, but never run any commands to deploy.
Deploy gRPC server with `--use-http2` flag. Envoy proxy requires `auto_host_rewrite: true` for Cloud Run routing. See README.md for full deployment commands.
