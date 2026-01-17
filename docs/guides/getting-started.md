# Getting Started

Local development setup for the AI Tasks Service.

## Prerequisites

- Python 3.11+ with [uv](https://docs.astral.sh/uv/)
- Docker (for Envoy proxy)
- `GOOGLE_API_KEY` environment variable

## Quick Start

### 1. Start the gRPC Server

```bash
cd server
uv run main.py
```

Server runs on `0.0.0.0:50051`. Must bind to `0.0.0.0` (not `127.0.0.1`) so Docker can reach it.

### 2. Start Envoy Proxy

```bash
docker run -p 8080:8080 \
  -v $(pwd)/envoy/envoy.local.yaml:/etc/envoy/envoy.yaml \
  envoyproxy/envoy:v1.28-latest
```

Envoy listens on `localhost:8080` and forwards to gRPC server on `host.docker.internal:50051`.

### 3. Connect Frontend

Point your gRPC-Web client to Envoy:

```typescript
const client = new AIServiceClient('http://localhost:8080');
```

## Generating Protobufs

After modifying `protobufs/ai_service.proto`, regenerate the code:

**Server (Python):**
```bash
uv run python -m grpc_tools.protoc -I protobufs --python_out=server --pyi_out=server --grpc_python_out=server ai_service.proto
```

**Client (Python):**
```bash
uv run python -m grpc_tools.protoc -I protobufs --python_out=client --pyi_out=client --grpc_python_out=client ai_service.proto
```

**Frontend (gRPC-Web):**
```bash
protoc -I=protobufs ai_service.proto \
  --js_out=import_style=commonjs:./frontend/src/generated \
  --grpc-web_out=import_style=typescript,mode=grpcwebtext:./frontend/src/generated
```

## Running Tests

```bash
uv run pytest
```

## Docker Build

```bash
docker build -t ai-tasks-service .
docker run -p 50051:50051 -e GOOGLE_API_KEY=your-key ai-tasks-service
```
