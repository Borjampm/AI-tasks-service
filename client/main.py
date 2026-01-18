"""gRPC client for interactive chat with AI service.

This CLI client provides an interactive conversation interface to the gRPC chat service
with streaming response support and session management. It automatically selects SSL or
insecure channels based on the target URL.

Usage:
    # Local development (insecure channel):
    SERVICE_URL=localhost:50051 uv run main.py

    # Remote/production (SSL channel):
    SERVICE_URL=your-service.run.app:443 uv run main.py

Commands during conversation:
    - 'new'  : Start a new conversation (resets session)
    - 'quit' : Exit the program
"""

import grpc
import grpc.aio
import chat_service_pb2, chat_service_pb2_grpc
import os
import asyncio
from dotenv import load_dotenv
load_dotenv()

SERVICE_URL = os.getenv("SERVICE_URL", "localhost:50051")
print(f"Connecting to service at {SERVICE_URL}")


LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1", "0.0.0.0")


def is_local_url(url: str) -> bool:
    """Determine if a URL points to a local/localhost service.

    Checks if the URL's host matches common localhost addresses to decide
    whether to use an insecure gRPC channel (local) or SSL credentials (remote).

    Args:
        url: Service URL in format "host:port" (e.g., "localhost:50051").

    Returns:
        True if URL is a local address, False for remote addresses.

    Examples:
        >>> is_local_url("localhost:50051")
        True
        >>> is_local_url("127.0.0.1:8080")
        True
        >>> is_local_url("example.com:443")
        False
    """
    if url.startswith("::1"):
        return True
    host = url.split(":")[0]
    return host in LOCAL_HOSTS or host.startswith("127.")


async def run_conversation(stub):
    """Run an interactive chat conversation with streaming responses.

    Manages conversation state through session IDs, allowing users to maintain
    conversation context across multiple messages. The session ID is automatically
    tracked and sent with each request. Users can reset the session with 'new' command.

    Streaming responses are printed character-by-character as they arrive from the server,
    providing real-time feedback. The conversation loop continues until the user types
    'quit' or sends EOF (Ctrl+D).

    Args:
        stub: ChatServiceStub instance for making gRPC calls.

    Raises:
        grpc.aio.AioRpcError: Printed to console if streaming call fails.
    """
    session_id = ""
    print("\nConversation started. Commands:")
    print("  'new'  - Start a new conversation")
    print("  'quit' - Exit the program\n")

    while True:
        try:
            message = await asyncio.to_thread(input, "You: ")
            message = message.strip()
        except EOFError:
            break

        if not message:
            continue

        if message.lower() == "quit":
            print("Goodbye!")
            break

        if message.lower() == "new":
            session_id = ""
            print("Started new conversation.\n")
            continue

        print("Assistant: ", end="", flush=True)
        try:
            async for response in stub.Chat(
                chat_service_pb2.ChatRequest(message=message, session_id=session_id)
            ):
                print(response.message, end="", flush=True)
                if response.session_id:
                    session_id = response.session_id
            print()
        except grpc.aio.AioRpcError as e:
            print(f"\nError: {e.code().name} - {e.details()}")


async def main():
    """Initialize gRPC channel and start conversation loop.

    Creates either an insecure or SSL-secured gRPC channel based on SERVICE_URL:
    - Local URLs (localhost, 127.0.0.1, etc.): Uses insecure_channel for development
    - Remote URLs: Uses secure_channel with SSL credentials for production

    The channel is managed as an async context manager to ensure proper cleanup
    on exit. SERVICE_URL is read from environment variable (defaults to localhost:50051).

    SSL Channel Logic:
        - Local development doesn't require SSL certificates
        - Production deployments (Cloud Run, etc.) require SSL
        - grpc.ssl_channel_credentials() uses system root certificates
    """
    if is_local_url(SERVICE_URL):
        channel = grpc.aio.insecure_channel(SERVICE_URL)
    else:
        credentials = grpc.ssl_channel_credentials()
        channel = grpc.aio.secure_channel(SERVICE_URL, credentials)

    async with channel:
        stub = chat_service_pb2_grpc.ChatServiceStub(channel)
        await run_conversation(stub)


if __name__ == "__main__":
    asyncio.run(main())
