# Copyright (c) 2025 ByteDance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""Doubao client wrapper with tool integrations"""

import openai

from trae_agent.utils.config import ModelConfig
from trae_agent.utils.llm_clients.openai_compatible_base import (
    OpenAICompatibleClient,
    ProviderConfig,
)


class ZhipuaiProvider(ProviderConfig):
    """Zhipuai provider configuration."""

    def create_client(
        self, api_key: str, base_url: str | None, api_version: str | None
    ) -> openai.OpenAI:
        """Create OpenAI client with Zhipuai base URL."""
        return openai.OpenAI(base_url=base_url, api_key=api_key)

    def get_service_name(self) -> str:
        """Get the service name for retry logging."""
        return "Zhipuai"

    def get_provider_name(self) -> str:
        """Get the provider name for trajectory recording."""
        return "zhipuai"

    def get_extra_headers(self) -> dict[str, str]:
        """Get Zhipuai-specific headers (none needed)."""
        return {}

    def supports_tool_calling(self, model_name: str) -> bool:
        """Check if the model supports tool calling."""
        # Zhipuai models generally support tool calling
        return True


class ZhipuaiClient(OpenAICompatibleClient):
    """Zhipuai client wrapper that maintains compatibility while using the new architecture."""

    def __init__(self, model_config: ModelConfig):
        super().__init__(model_config, ZhipuaiProvider())
