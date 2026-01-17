# Production Deployment

Deploying the AI Tasks Service to Google Cloud Run.

## Overview

Production deployment consists of two services:
1. **gRPC Server** - The main AI service
2. **Envoy Proxy** - Translates gRPC-Web to gRPC for browser clients

## Deploy gRPC Server

```bash
gcloud run deploy ai-tasks-service \
  --source . \
  --use-http2 \
  --port 50051 \
  --region us-central1 \
  --allow-unauthenticated
```

## Deploy Envoy Proxy

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
  --set-env-vars="FRONTEND_URL=https://your-frontend.com,GRPC_HOST=ai-tasks-service-xxxxx.us-central1.run.app,GRPC_PORT=443"
```

**Note:** `GRPC_HOST` should be the hostname only, without `https://`.

## Frontend Configuration

```typescript
const GRPC_URL = import.meta.env.PROD
  ? 'https://envoy-proxy-xxxxx.run.app'
  : 'http://localhost:8080';

const client = new AIServiceClient(GRPC_URL);
```

## Troubleshooting

### Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| CORS error | Envoy not running or `FRONTEND_URL` mismatch | Check Envoy is running, verify exact origin match |
| `connection refused (111)` | gRPC server not running | Start server, ensure it binds to `0.0.0.0` |
| `upstream connect error` | Envoy can't reach gRPC server | Check host/port config |
| `remote reset` after 30s | Missing `auto_host_rewrite` | Add `auto_host_rewrite: true` to route config |

### Debug Commands

**Check Envoy logs:**
```bash
gcloud run services logs read envoy-proxy --region us-central1 --limit 50
```

**Check gRPC service logs:**
```bash
gcloud run services logs read ai-tasks-service --region us-central1 --limit 50
```

**Verify environment variables:**
```bash
gcloud run services describe envoy-proxy --region us-central1 --format="yaml(spec.template.spec.containers[0].env)"
```

**Test gRPC service directly:**
```bash
grpcurl -proto protobufs/ai_service.proto \
  -d '{"question": "test"}' \
  ai-tasks-service-xxxxx.us-central1.run.app:443 \
  ai_service.AIService/QA
```

**Enable verbose Envoy logging:**
Update `entrypoint.sh`:
```bash
exec envoy -c /etc/envoy/envoy.yaml -l debug
```

## Key Configuration Notes

1. **`auto_host_rewrite: true` is required** — Cloud Run uses the Host header to route requests
2. **CORS must match exactly** — Use `exact:` instead of `prefix:` for production
3. **gRPC needs HTTP/2** — Ensure `http2_protocol_options` is set in Envoy cluster config
4. **TLS is required** — Production Envoy config needs `transport_socket` with TLS and correct `sni`
5. **DNS resolution** — Use `STRICT_DNS` locally, `LOGICAL_DNS` for Cloud Run
