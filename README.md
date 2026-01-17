# AI Tasks Service

A gRPC-based AI service for automations leveraging AI agents. Browser connectivity is handled via an Envoy proxy that translates gRPC-Web to gRPC.

## Architecture

```
Browser (gRPC-Web) → Envoy Proxy (:8080) → gRPC Server (:50051)
```

## Components

| Component | Purpose | Location |
|-----------|---------|----------|
| **gRPC Server** | Async Python server exposing AI agents | `server/` |
| **Envoy Proxy** | gRPC-Web to gRPC translation + CORS | `envoy/` |
| **Database Module** | Secure read-only Supabase access for AI agents | `server/database/` |
| **AI Agents** | Pydantic AI agents (chat, database query) | `server/agents/` |

## Quick Start

```bash
# Start gRPC server
cd server && uv run main.py

# Start Envoy proxy (separate terminal)
docker run -p 8080:8080 \
  -v $(pwd)/envoy/envoy.local.yaml:/etc/envoy/envoy.yaml \
  envoyproxy/envoy:v1.28-latest
```

## Documentation

| Guide | Description |
|-------|-------------|
| [Getting Started](docs/guides/getting-started.md) | Local development setup, protobuf generation, testing |
| [Deployment](docs/guides/deployment.md) | Cloud Run deployment, troubleshooting, configuration |
| [Database Module](docs/components/database.md) | DatabaseManager, QueryExecutor, SchemaDiscovery |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_API_KEY` | Yes | API key for Gemini AI model |
| `DATABASE_URL` | For database agent | Supabase PostgreSQL connection string |
| `PORT` | No | gRPC server port (default: 50051) |

## Testing

```bash
uv run pytest
```
