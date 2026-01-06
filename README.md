# How to generate the protobufs:

```bash
uv run python -m grpc_tools.protoc -I. --python_out=. --pyi_out=. --grpc_python_out=. service.proto
```
where:
- `-I.` is the input directory
- `--python_out=.` is the output directory for message classes
- `--pyi_out=.` is the output directory for type stubs
- `--grpc_python_out=.` is the output directory for grpc service classes
- `service.proto` is the input file

It generates the following files:
- `service_pb2.py` - message classes
- `service_pb2_grpc.py` - grpc service classes
- `service_pb2.pyi` - type stubs

To create the client rpc files, run the following command:

```bash
uv run python -m grpc_tools.protoc -I protobufs --python_out=client --pyi_out=client --grpc_python_out=client ai_service.proto
```

To create the server rpc files, run the following command:

```bash
uv run python -m grpc_tools.protoc -I protobufs --python_out=server --pyi_out=server --grpc_python_out=server ai_service.proto
```

# How to run:

## How to run the server:

```bash
cd server
uv run main.py
```

## How to run the client:

```bash
cd client
uv run main.py
```

## With docker:

```bash 
docker build -t ai-tasks-service .
docker run -p 50051:50051 -e GOOGLE_API_KEY=your-key ai-tasks-service
```

# Cloud Run Deployment:

```bash
gcloud run deploy ai-tasks-service \
  --source . \
  --use-http2 \
  --port 50051 \
  --region=us-central1 \
  --allow-unauthenticated
```