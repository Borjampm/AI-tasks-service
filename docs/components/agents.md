# AI Agents Module

Pydantic AI agents that power the gRPC service. Currently provides a chat agent using Google's Gemma model for conversational AI.

## Purpose

This module configures and exports AI agents that the gRPC server uses to process user requests. Agents handle the actual AI inference, streaming responses, and conversation context management.

## Key Concepts

- **Agent**: A Pydantic AI wrapper around an AI model with streaming support
- **Model**: The underlying AI model (Gemma 3 27B)
- **Provider**: Connection to the AI service (Google AI Platform)
- **Streaming**: Real-time token-by-token response generation

## Available Agents

### chat_agent (`agents/chat.py`)

Conversational AI agent using Google's Gemma 3 27B model.

```python
from agents import chat_agent

# Streaming conversation
async with chat_agent.run_stream(
    "What is the capital of France?",
    message_history=previous_messages
) as result:
    async for text in result.stream_text(delta=True):
        print(text, end="")

    # Get complete message history for storage
    all_messages = result.all_messages()
```

**Capabilities:**
- Streaming text responses for real-time display
- Message history support for multi-turn conversations
- Async context manager for resource cleanup

**Model Configuration:**
| Setting | Value |
|---------|-------|
| Model | `gemma-3-27b-it` |
| Provider | Google AI Platform |
| Framework | Pydantic AI |

## Usage

### In the gRPC Server

The chat agent is imported and used by the ChatServiceServicer:

```python
from agents import chat_agent

async def Chat(self, request, context):
    history = await session_store.get_history(session_id)

    async with chat_agent.run_stream(
        request.message,
        message_history=history
    ) as result:
        async for text in result.stream_text(delta=True):
            yield ChatResponse(message=text)
```

### Standalone Usage

```python
import asyncio
from agents import chat_agent

async def main():
    result = await chat_agent.run("Hello, how are you?")
    print(result.output)

asyncio.run(main())
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_API_KEY` | Yes | API key for Google AI Platform access |

The module raises `EnvironmentError` at import time if `GOOGLE_API_KEY` is not set.

## Architecture Decisions

**Why Gemma 3 27B?**
- Open-weights model suitable for production use
- Instruction-tuned variant (`-it`) for conversational tasks
- Good balance of quality and inference speed

**Why Pydantic AI?**
- Type-safe agent configuration
- Built-in streaming support
- Clean async context manager pattern
- Integration with Logfire for observability

## Extending

To add a new agent:

1. Create a new file in `server/agents/` (e.g., `database.py`)
2. Configure the agent with appropriate model and tools
3. Export from `server/agents/__init__.py`
4. Use in the gRPC servicer

Example structure for a new agent:

```python
# server/agents/new_agent.py
from pydantic_ai import Agent

new_agent = Agent(
    model=...,
    tools=[...],
    system_prompt="..."
)
```

## See Also

- [Server Module](server.md) - How agents are used in the gRPC server
- [Database Module](database.md) - Database access for data-aware agents
- [Pydantic AI Documentation](https://docs.pydantic.dev/pydantic-ai/) - Framework documentation
