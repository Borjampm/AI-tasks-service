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

## Envoy Configuration

### Local (`envoy/envoy.local.yaml`)

```yaml
static_resources:
  listeners:
    - name: listener_0
      address:
        socket_address:
          address: 0.0.0.0
          port_value: 8080
      filter_chains:
        - filters:
            - name: envoy.filters.network.http_connection_manager
              typed_config:
                "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
                codec_type: auto
                stat_prefix: ingress_http
                route_config:
                  name: local_route
                  virtual_hosts:
                    - name: local_service
                      domains: ["*"]
                      cors:
                        allow_origin_string_match:
                          - exact: "http://localhost:5173"
                        allow_methods: GET, POST, OPTIONS
                        allow_headers: content-type,x-grpc-web,x-user-agent,grpc-timeout,authorization
                        expose_headers: grpc-status,grpc-message
                        max_age: "1728000"
                      routes:
                        - match:
                            prefix: "/"
                          route:
                            cluster: grpc_backend
                            timeout: 0s
                http_filters:
                  - name: envoy.filters.http.grpc_web
                    typed_config:
                      "@type": type.googleapis.com/envoy.extensions.filters.http.grpc_web.v3.GrpcWeb
                  - name: envoy.filters.http.cors
                    typed_config:
                      "@type": type.googleapis.com/envoy.extensions.filters.http.cors.v3.Cors
                  - name: envoy.filters.http.router
                    typed_config:
                      "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router

  clusters:
    - name: grpc_backend
      type: STRICT_DNS
      lb_policy: ROUND_ROBIN
      typed_extension_protocol_options:
        envoy.extensions.upstreams.http.v3.HttpProtocolOptions:
          "@type": type.googleapis.com/envoy.extensions.upstreams.http.v3.HttpProtocolOptions
          explicit_http_config:
            http2_protocol_options: {}
      load_assignment:
        cluster_name: grpc_backend
        endpoints:
          - lb_endpoints:
              - endpoint:
                  address:
                    socket_address:
                      address: host.docker.internal
                      port_value: 50051
```

### Production (`envoy/envoy.template.yaml`)

Uses environment variables substituted at runtime via `envsubst`:

```yaml
static_resources:
  listeners:
    - name: listener_0
      address:
        socket_address:
          address: 0.0.0.0
          port_value: 8080
      filter_chains:
        - filters:
            - name: envoy.filters.network.http_connection_manager
              typed_config:
                "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
                codec_type: auto
                stat_prefix: ingress_http
                route_config:
                  name: local_route
                  virtual_hosts:
                    - name: local_service
                      domains: ["*"]
                      cors:
                        allow_origin_string_match:
                          - exact: "${FRONTEND_URL}"
                        allow_methods: GET, POST, OPTIONS
                        allow_headers: content-type,x-grpc-web,x-user-agent,grpc-timeout,authorization
                        expose_headers: grpc-status,grpc-message
                        max_age: "1728000"
                      routes:
                        - match:
                            prefix: "/"
                          route:
                            cluster: grpc_backend
                            timeout: 0s
                            auto_host_rewrite: true
                http_filters:
                  - name: envoy.filters.http.grpc_web
                    typed_config:
                      "@type": type.googleapis.com/envoy.extensions.filters.http.grpc_web.v3.GrpcWeb
                  - name: envoy.filters.http.cors
                    typed_config:
                      "@type": type.googleapis.com/envoy.extensions.filters.http.cors.v3.Cors
                  - name: envoy.filters.http.router
                    typed_config:
                      "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router

  clusters:
    - name: grpc_backend
      connect_timeout: 5s
      type: LOGICAL_DNS
      lb_policy: ROUND_ROBIN
      dns_lookup_family: V4_ONLY
      typed_extension_protocol_options:
        envoy.extensions.upstreams.http.v3.HttpProtocolOptions:
          "@type": type.googleapis.com/envoy.extensions.upstreams.http.v3.HttpProtocolOptions
          explicit_http_config:
            http2_protocol_options: {}
      load_assignment:
        cluster_name: grpc_backend
        endpoints:
          - lb_endpoints:
              - endpoint:
                  address:
                    socket_address:
                      address: ${GRPC_HOST}
                      port_value: ${GRPC_PORT}
      transport_socket:
        name: envoy.transport_sockets.tls
        typed_config:
          "@type": type.googleapis.com/envoy.extensions.transport_sockets.tls.v3.UpstreamTlsContext
          sni: ${GRPC_HOST}
```

**Key differences from local:**
- `LOGICAL_DNS` instead of `STRICT_DNS` for Cloud Run hostnames
- `auto_host_rewrite: true` — **Critical!** Cloud Run uses the Host header for routing
- TLS enabled via `transport_socket`
- Port 443 for HTTPS
- Environment variables for configuration

### Envoy Dockerfile (`envoy/Dockerfile`)

```dockerfile
FROM envoyproxy/envoy:v1.28-latest

RUN apt-get update && apt-get install -y gettext-base && rm -rf /var/lib/apt/lists/*

COPY envoy.template.yaml /etc/envoy/envoy.template.yaml
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
```

### Entrypoint (`envoy/entrypoint.sh`)

```bash
#!/bin/sh
envsubst '${FRONTEND_URL} ${GRPC_HOST} ${GRPC_PORT}' < /etc/envoy/envoy.template.yaml > /etc/envoy/envoy.yaml
exec envoy -c /etc/envoy/envoy.yaml
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
  --set-env-vars="FRONTEND_URL=https://your-frontend.com,GRPC_HOST=ai-tasks-service-xxxxx.us-central1.run.app,GRPC_PORT=443"
```

**Note:** `GRPC_HOST` should be the hostname only, without `https://`.

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

### Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| CORS error | Envoy not running or `FRONTEND_URL` mismatch | Check Envoy is running, verify exact origin match |
| `connection refused (111)` | gRPC server not running | Start server, ensure it binds to `0.0.0.0` |
| `upstream connect error` | Envoy can't reach gRPC server | Check host/port config, see debugging below |
| `remote reset` after 30s | Missing `auto_host_rewrite` | Add `auto_host_rewrite: true` to route config |

### Production Debugging

#### 1. Check Envoy logs
```bash
gcloud run services logs read envoy-proxy --region us-central1 --limit 50
```

Look for:
- `grpc-status: 14` — upstream connection failed
- `reset reason: remote reset` — backend rejected connection
- `upstream_reset` or `timeout` — connectivity issues

#### 2. Check gRPC service logs
```bash
gcloud run services logs read ai-tasks-service --region us-central1 --limit 50
```

Look for:
- `Error parsing ':method' metadata` — HTTP/2 mismatch
- No incoming requests — Envoy can't reach the service

#### 3. Verify environment variables
```bash
gcloud run services describe envoy-proxy --region us-central1 --format="yaml(spec.template.spec.containers[0].env)"
```

Confirm `GRPC_HOST`, `GRPC_PORT`, and `FRONTEND_URL` are correct.

#### 4. Test gRPC service directly
```bash
# Install grpcurl
brew install grpcurl

# Test with your proto file
grpcurl -proto protobufs/ai_service.proto \
  -d '{"question": "test"}' \
  ai-tasks-service-xxxxx.us-central1.run.app:443 \
  ai_service.AIService/QA
```

If this works but Envoy doesn't, the issue is Envoy config (likely `auto_host_rewrite`).

#### 5. Test Envoy is reachable
```bash
curl -v https://envoy-proxy-xxxxx.run.app
```

Should return a gRPC error (not connection refused).

#### 6. Debug with verbose Envoy logging

Update `entrypoint.sh` to enable debug logs:
```bash
exec envoy -c /etc/envoy/envoy.yaml -l debug
```

Rebuild and redeploy, then check logs for detailed connection info.

---

## Key Lessons Learned

1. **`auto_host_rewrite: true` is required for Cloud Run** — Cloud Run uses the Host header to route requests. Without this, requests from Envoy get lost.

2. **CORS must match exactly** — Use `exact:` instead of `prefix:` for production security.

3. **gRPC needs HTTP/2** — Ensure `http2_protocol_options` is set in the Envoy cluster config.

4. **TLS is required for Cloud Run** — Production Envoy config needs `transport_socket` with TLS and correct `sni`.

5. **Use `STRICT_DNS` locally, `LOGICAL_DNS` for Cloud Run** — Different DNS resolution strategies for different environments.
