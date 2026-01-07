# AI Tasks Service

A gRPC-based AI service with Envoy proxy for browser (gRPC-Web) connectivity.

## Architecture
```
Browser (gRPC-Web) → Envoy Proxy → gRPC Server
```

- **gRPC Server**: Python async server using `grpc.aio`
- **Envoy Proxy**: Translates gRPC-Web (HTTP/1.1) to gRPC (HTTP/2) and handles CORS

---

## Generating Protobufs

### Server (Python)
```bash
uv run python -m grpc_tools.protoc -I protobufs --python_out=server --pyi_out=server --grpc_python_out=server ai_service.proto
```

### Client (Python)
```bash
uv run python -m grpc_tools.protoc -I protobufs --python_out=client --pyi_out=client --grpc_python_out=client ai_service.proto
```

### Frontend (gRPC-Web)
```bash
protoc -I=protobufs ai_service.proto \
  --js_out=import_style=commonjs:./frontend/src/generated \
  --grpc-web_out=import_style=typescript,mode=grpcwebtext:./frontend/src/generated
```

**Flags explained:**
- `-I.` — input directory
- `--python_out=.` — output directory for message classes
- `--pyi_out=.` — output directory for type stubs
- `--grpc_python_out=.` — output directory for gRPC service classes
- `--js_out` — JavaScript message classes
- `--grpc-web_out` — gRPC-Web client stubs

---

## Local Development

### 1. Start the gRPC Server
```bash
cd server
uv run main.py
```

Server runs on `0.0.0.0:50051`. Make sure it binds to `0.0.0.0`, not `127.0.0.1`, so Docker can reach it.

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

---

## Production Deployment (Cloud Run)

### Deploy gRPC Server
```bash
gcloud run deploy ai-tasks-service \
  --source . \
  --use-http2 \
  --port 50051 \
  --region us-central1 \
  --allow-unauthenticated
```

### Deploy Envoy Proxy
```bash
# Build and push image
cd envoy
gcloud builds submit --tag gcr.io/ai-tasks-service/envoy-proxy

# Deploy with environment variables
gcloud run deploy envoy-proxy \
  --image gcr.io/ai-tasks-service/envoy-proxy \
  --port 8080 \
  --allow-unauthenticated \
  --region us-central1 \
  --set-env-vars="FRONTEND_URL=https://your-frontend.com,GRPC_HOST=url-to-grpc-with-no-https,GRPC_PORT=443"
```

### Frontend Configuration
```typescript
const GRPC_URL = import.meta.env.PROD 
  ? 'https://envoy-proxy-xxxxx.run.app'
  : 'http://localhost:8080';

const client = new AIServiceClient(GRPC_URL);
```

---

## Docker (gRPC Server Only)
```bash
docker build -t ai-tasks-service .
docker run -p 50051:50051 -e GOOGLE_API_KEY=your-key ai-tasks-service
```

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| CORS error | Envoy not running or misconfigured | Check Envoy is running on :8080 |
| `connection refused (111)` | gRPC server not running | Start server, ensure it binds to `0.0.0.0` |
| `upstream connect error` | Envoy can't reach gRPC server | Check port and host configuration |