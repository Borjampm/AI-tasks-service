"""Pydantic AI agents for the gRPC service.

This package provides pre-configured AI agents for various tasks:

- chat_agent: General-purpose conversational agent using Google's Gemma 3 27B model.

All agents are initialized at import time and ready for use in gRPC service handlers.
"""

from .chat import chat_agent

__all__ = ["chat_agent"]