# syntax=docker/dockerfile:1

FROM python:3.13-slim AS builder

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-install-project --no-dev

# Copy protobufs and generate Python files
COPY protobufs/ ./protobufs/
RUN mkdir -p ./server

RUN .venv/bin/python -m grpc_tools.protoc \
    -I./protobufs \
    --python_out=./server \
    --pyi_out=./server \
    --grpc_python_out=./server \
    ./protobufs/ai_service.proto

# Copy server code
COPY server/ ./server/

# Production stage
FROM python:3.13-slim

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy server code (includes generated protobuf files)
COPY --from=builder /app/server ./server/

# Add venv to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Cloud Run sets PORT env var, default to 50051 for gRPC
ENV PORT=50051

WORKDIR /app/server

# Run the gRPC server
CMD ["python", "main.py"]
