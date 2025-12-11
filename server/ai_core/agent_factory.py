from pydantic_ai import Agent

from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from google.genai import Client
import os
from dotenv import load_dotenv
from pydantic_ai.tools import AgentDepsT

import logfire

logfire.configure()  
logfire.instrument_pydantic_ai()

load_dotenv()

class ModelDoesNotExistError(Exception):
    """
    Exception raised when a model does not exist.
    """
    def __init__(self, model: str):
        self.model = model
        super().__init__(f"Model {model} does not exist")

class ProviderNotFoundError(Exception):
    """
    Exception raised when a provider is not found.
    """
    def __init__(self, model: str):
        self.model = model
        super().__init__(f"Provider for model {model} not found")


class AgentFactory:
    def __init__(self):
        self._available_models: dict[str, list[str]] = {
            'google': [
                'gemma-3-27b-it',
                'gemini-2.5-flash-lite',
            ],
        }
        self._agents: dict[str, Agent] = {}

    def get_available_models(self) -> list[str]:
        """
        Get the available models.

        Returns:
            - A list of available models.
        
        """
        models_list = []
        for provider, models in self._available_models.items():
            models_list.extend(models)
        return models_list

    def get_agent(self, model: str) -> Agent:
        """
        Get an agent for a given model.

        Args:
            - model: The model to get an agent for.

        Returns:
            - An agent for the given model.

        Raises:
            - ModelDoesNotExistError: If the model does not exist.
        """
        self._check_if_model_exists(model)
        try:
            return self._agents[model]
        except KeyError:
            print(f"Model {model} not found, creating new agent")
            agent = self._create_new_agent(model)
            self._store_agent(model, agent)
            return agent

    def _check_if_model_exists(self, model: str) -> None:
        """
        Check if a model exists.

        Args:
            - model: The model to check if it exists.
        """
        for provider, models in self._available_models.items():
            if model in models:
                return
        raise ModelDoesNotExistError(model)

    def _create_new_agent(self, model: str) -> AgentDepsT:
        """
        Create a new agent for a given model.

        Args:
            - model: The model to create an agent for.

        Raises:
            - NotImplementedError: If the provider has not been implemented.
        """
        provider = self._find_provider_of_model(model)
        match provider:
            case 'google':
                return self._create_new_google_agent(model)
            case _:
                raise NotImplementedError(f"Provider has not been implemented: {provider}")

    def _find_provider_of_model(self, model: str) -> str:
        """
        Find the provider of a given model.

        Args:
            - model: The model to find the provider of.
        
        Returns:
            - The provider of the given model.

        Raises:
            - ProviderNotFoundError: If the provider is not found.
        """
        for provider, models in self._available_models.items():
            if model in models:
                return provider
        else:
            raise ProviderNotFoundError(model)

    def _create_new_google_agent(self, model: str) -> Agent:
        """
        Create a new Google agent for a given model.

        Args:
            - model: The model to create a Google agent for.

        Returns:
            - A new Google agent for the given model.
        """
        agent = Agent(GoogleModel(model, provider=GoogleProvider(
            client=Client(api_key=os.getenv('GOOGLE_API_KEY'))
        )))
        return agent

    def _store_agent(self, model: str, agent: Agent) -> None:
        """
        Store an agent for a given model.

        Args:
            - model: The model to store the agent for.
            - agent: The agent to store.
        """
        self._agents[model] = agent

if __name__ == "__main__":
    agent_factory = AgentFactory()
    print(agent_factory.get_available_models())
    print(agent_factory.get_agent('gemma-3-27b-it'))