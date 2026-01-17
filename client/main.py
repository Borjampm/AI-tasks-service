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
    if url.startswith("::1"):
        return True
    host = url.split(":")[0]
    return host in LOCAL_HOSTS or host.startswith("127.")


async def run_conversation(stub):
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
