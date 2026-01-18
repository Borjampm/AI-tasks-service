"""Unit tests for chat_agent module."""

import pytest
import sys
import importlib
from unittest.mock import MagicMock, patch
from pathlib import Path


SERVER_PATH = Path(__file__).parent.parent.parent.parent / "server"


class TestChatAgentInitialization:
    """Tests for chat_agent module initialization."""

    def test_raises_environment_error_when_google_api_key_missing(self):
        """Agent should raise EnvironmentError when GOOGLE_API_KEY is not set."""
        # Clear any cached module
        modules_to_remove = [
            key for key in sys.modules.keys()
            if "agents" in key or "chat" in key
        ]
        for mod in modules_to_remove:
            del sys.modules[mod]

        server_path_str = str(SERVER_PATH)
        if server_path_str not in sys.path:
            sys.path.insert(0, server_path_str)

        # Mock environment without GOOGLE_API_KEY
        with patch.dict("os.environ", {}, clear=True):
            with patch("dotenv.load_dotenv"):
                with pytest.raises(EnvironmentError) as exc_info:
                    # Force reimport
                    if "agents.chat" in sys.modules:
                        del sys.modules["agents.chat"]
                    if "agents" in sys.modules:
                        del sys.modules["agents"]

                    import importlib.util
                    spec = importlib.util.spec_from_file_location(
                        "agents.chat",
                        SERVER_PATH / "agents" / "chat.py"
                    )
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                assert "GOOGLE_API_KEY" in str(exc_info.value)

    def test_initializes_with_correct_model(self):
        """Agent should initialize with gemma-3-27b-it model."""
        # Clear cached modules
        modules_to_remove = [
            key for key in sys.modules.keys()
            if "agents" in key or "chat" in key
        ]
        for mod in modules_to_remove:
            del sys.modules[mod]

        server_path_str = str(SERVER_PATH)
        if server_path_str not in sys.path:
            sys.path.insert(0, server_path_str)

        mock_agent = MagicMock()
        mock_google_model = MagicMock()
        mock_google_provider = MagicMock()
        mock_client = MagicMock()

        with patch.dict("os.environ", {"GOOGLE_API_KEY": "test-api-key"}):
            with patch("dotenv.load_dotenv"):
                with patch("pydantic_ai.Agent", return_value=mock_agent) as agent_class:
                    with patch("pydantic_ai.models.google.GoogleModel", return_value=mock_google_model) as model_class:
                        with patch("pydantic_ai.providers.google.GoogleProvider", return_value=mock_google_provider) as provider_class:
                            with patch("google.genai.Client", return_value=mock_client) as client_class:
                                import importlib.util
                                spec = importlib.util.spec_from_file_location(
                                    "agents.chat_test",
                                    SERVER_PATH / "agents" / "chat.py"
                                )
                                module = importlib.util.module_from_spec(spec)
                                spec.loader.exec_module(module)

                                # Verify GoogleModel was called with correct model name
                                model_class.assert_called_once()
                                call_kwargs = model_class.call_args
                                assert call_kwargs[1]["model_name"] == "gemma-3-27b-it"

    def test_uses_google_provider_with_client(self):
        """Agent should use GoogleProvider with Client initialized with API key."""
        # Clear cached modules
        modules_to_remove = [
            key for key in sys.modules.keys()
            if "agents" in key or "chat" in key
        ]
        for mod in modules_to_remove:
            del sys.modules[mod]

        server_path_str = str(SERVER_PATH)
        if server_path_str not in sys.path:
            sys.path.insert(0, server_path_str)

        mock_agent = MagicMock()
        mock_google_model = MagicMock()
        mock_google_provider = MagicMock()
        mock_client = MagicMock()

        with patch.dict("os.environ", {"GOOGLE_API_KEY": "test-api-key-123"}):
            with patch("dotenv.load_dotenv"):
                with patch("pydantic_ai.Agent", return_value=mock_agent):
                    with patch("pydantic_ai.models.google.GoogleModel", return_value=mock_google_model):
                        with patch("pydantic_ai.providers.google.GoogleProvider", return_value=mock_google_provider) as provider_class:
                            with patch("google.genai.Client", return_value=mock_client) as client_class:
                                import importlib.util
                                spec = importlib.util.spec_from_file_location(
                                    "agents.chat_test2",
                                    SERVER_PATH / "agents" / "chat.py"
                                )
                                module = importlib.util.module_from_spec(spec)
                                spec.loader.exec_module(module)

                                # Verify Client was created with API key
                                client_class.assert_called_once_with(api_key="test-api-key-123")

                                # Verify GoogleProvider was created with the client
                                provider_class.assert_called_once()
                                provider_call = provider_class.call_args
                                assert provider_call[1]["client"] == mock_client
