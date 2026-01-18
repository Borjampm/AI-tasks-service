# Client Module

Interactive CLI client for testing the gRPC chat service with streaming responses and session management.

## Purpose

This module provides a command-line interface for developers to test and interact with the chat service. It handles connection management, session tracking, and displays streaming responses in real-time.

## Key Concepts

- **Streaming Responses**: Responses are printed character-by-character as they arrive
- **Session Tracking**: Session ID is automatically captured and sent with each request
- **SSL Detection**: Automatically selects secure or insecure channels based on URL

## Capabilities

- Interactive chat loop with real-time streaming output
- Automatic session persistence across messages
- Session reset via 'new' command
- SSL for production, insecure for local development

## Usage

### Local Development

```bash
cd client && uv run main.py
# or
SERVICE_URL=localhost:50051 uv run main.py
```

### Remote/Production

```bash
SERVICE_URL=your-service.run.app:443 uv run main.py
```

### Interactive Commands

| Command | Action |
|---------|--------|
| `new` | Start a new conversation (resets session) |
| `quit` | Exit the program |
| Ctrl+D | Exit the program (EOF) |

### Example Session

```
Connecting to service at localhost:50051

Conversation started. Commands:
  'new'  - Start a new conversation
  'quit' - Exit the program

You: What is the capital of France?
Assistant: The capital of France is Paris.
You: What is its population?
Assistant: Paris has a population of approximately 2.1 million people in the city proper, and about 12 million in the greater metropolitan area.
You: new
Started new conversation.

You: quit
Goodbye!
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVICE_URL` | `localhost:50051` | gRPC server address |

## Architecture Decisions

**Why automatic SSL detection?**
Local development typically runs without TLS certificates. Rather than requiring manual flags, the client detects localhost addresses and uses insecure channels. Production URLs automatically use SSL.

**Local addresses detected:**
- `localhost`
- `127.0.0.1`
- `::1`
- `0.0.0.0`
- Any address starting with `127.`

**Why async with grpc.aio?**
- Non-blocking I/O for streaming responses
- Clean resource management with async context managers
- Consistent with async gRPC server

## Connection Flow

```
┌─────────────────┐
│ Parse SERVICE_URL│
└────────┬────────┘
         │
         ▼
┌─────────────────┐    Yes    ┌─────────────────┐
│ Is local URL?   │──────────▶│ insecure_channel│
└────────┬────────┘           └─────────────────┘
         │ No
         ▼
┌─────────────────┐
│ secure_channel  │
│ (SSL credentials)│
└─────────────────┘
```

## Error Handling

gRPC errors are caught and displayed with status code and details:

```
You: hello
Assistant:
Error: UNAVAILABLE - failed to connect to all addresses
```

Common error codes:
| Code | Meaning |
|------|---------|
| `UNAVAILABLE` | Server not reachable |
| `INTERNAL` | Server-side error |
| `DEADLINE_EXCEEDED` | Request timeout |

## See Also

- [Server Module](server.md) - The gRPC server this client connects to
- [Getting Started](../guides/getting-started.md) - Development setup
- [Deployment](../guides/deployment.md) - Production configuration
