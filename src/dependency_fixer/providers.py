import os
from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic_ai.models import Model
from pydantic_ai.models.bedrock import BedrockConverseModel, BedrockModelSettings
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.providers.bedrock import BedrockProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.providers.openrouter import OpenRouterProvider
from pydantic_ai.settings import ModelSettings

ReasoningEffort = Literal["minimal", "low", "medium", "high"]


class MissingEnvVar(ValueError):
    """A required environment variable for a Backend profile isn't set."""


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise MissingEnvVar(f"{name} must be set to use this profile")
    return value


class Backend(Protocol):
    """A way of reaching a model. Owns everything backend-specific: how to
    authenticate/connect, and how this particular API spells generic concepts
    like "reasoning effort" in its own `ModelSettings` dialect — callers only
    ever deal in `effort`/`temperature`, never in backend-specific field names."""

    def build_model(self) -> Model: ...

    def build_settings(self, *, effort: ReasoningEffort | None, temperature: float | None) -> ModelSettings: ...


@dataclass(frozen=True)
class BedrockBackend:
    """AWS Bedrock. Auth via `api_key` (falls back to `AWS_BEARER_TOKEN_BEDROCK`)
    or the standard AWS credential chain; region via `region_name` (falls back
    to `AWS_DEFAULT_REGION`)."""

    model_name: str
    region_name: str | None = None
    api_key: str | None = None

    def build_model(self) -> Model:
        provider = (
            BedrockProvider(api_key=self.api_key, region_name=self.region_name)
            if self.api_key is not None
            else BedrockProvider(region_name=self.region_name)
        )
        return BedrockConverseModel(self.model_name, provider=provider)

    def build_settings(self, *, effort: ReasoningEffort | None, temperature: float | None) -> ModelSettings:
        settings: BedrockModelSettings = {}
        if temperature is not None:
            settings["temperature"] = temperature
        if effort is not None:
            settings["thinking"] = effort
        return settings


@dataclass(frozen=True)
class OpenRouterBackend:
    """OpenRouter. Auth via `api_key` (falls back to `OPENROUTER_API_KEY`)."""

    model_name: str
    api_key: str | None = None

    def build_model(self) -> Model:
        provider = OpenRouterProvider(api_key=self.api_key)
        return OpenAIChatModel(self.model_name, provider=provider)

    def build_settings(self, *, effort: ReasoningEffort | None, temperature: float | None) -> ModelSettings:
        settings: OpenAIChatModelSettings = {}
        if temperature is not None:
            settings["temperature"] = temperature
        if effort is not None:
            settings["openai_reasoning_effort"] = effort
        return settings


@dataclass(frozen=True)
class OpenAICompatibleBackend:
    """Any OpenAI-chat-compatible server (vLLM, Ollama, LM Studio, ...) reached
    directly by URL — no provider-specific auth scheme, just a bearer `api_key`
    (if the server wants one) against an arbitrary `base_url`."""

    model_name: str
    base_url: str
    api_key: str | None = None

    def build_model(self) -> Model:
        provider = OpenAIProvider(base_url=self.base_url, api_key=self.api_key)
        return OpenAIChatModel(self.model_name, provider=provider)

    def build_settings(self, *, effort: ReasoningEffort | None, temperature: float | None) -> ModelSettings:
        settings: OpenAIChatModelSettings = {}
        if temperature is not None:
            settings["temperature"] = temperature
        if effort is not None:
            settings["openai_reasoning_effort"] = effort
        return settings


@dataclass(frozen=True)
class SelfHostedOpenAIBackend:
    """A self-hosted OpenAI-chat-compatible server, configured entirely from
    environment variables for a server that's
    specific to wherever this tool happens to be running, not something to bake
    a URL for into source. Read lazily (inside build_model/build_settings, not
    at PROFILES-construction/import time) so `.env` files loaded by the CLI
    (which happens inside main(), after `providers` is already imported) are
    picked up.

      - SELF_HOSTED_OPENAI_MODEL (required): the model name to request.
      - SELF_HOSTED_OPENAI_BASE_URL (required): the server's OpenAI-compatible
        base URL, e.g. "http://localhost:11434/v1".
      - SELF_HOSTED_OPENAI_API_KEY (optional): bearer token, if the server
        requires one.
    """

    def build_model(self) -> Model:
        model_name = _require_env("SELF_HOSTED_OPENAI_MODEL")
        base_url = _require_env("SELF_HOSTED_OPENAI_BASE_URL")
        api_key = os.environ.get("SELF_HOSTED_OPENAI_API_KEY")
        provider = OpenAIProvider(base_url=base_url, api_key=api_key)
        return OpenAIChatModel(model_name, provider=provider)

    def build_settings(self, *, effort: ReasoningEffort | None, temperature: float | None) -> ModelSettings:
        settings: OpenAIChatModelSettings = {}
        if temperature is not None:
            settings["temperature"] = temperature
        if effort is not None:
            settings["openai_reasoning_effort"] = effort
        return settings


PROFILES: dict[str, Backend] = {
    "bedrock-claude-sonnet": BedrockBackend(model_name="us.anthropic.claude-sonnet-4-5-20250929-v1:0"),
    "bedrock-llama-3.3-70b": BedrockBackend(model_name="us.meta.llama3-3-70b-instruct-v1:0"),
    "openrouter-claude-sonnet": OpenRouterBackend(model_name="anthropic/claude-sonnet-4.5"),
    "self-hosted-openai": SelfHostedOpenAIBackend(),
}
