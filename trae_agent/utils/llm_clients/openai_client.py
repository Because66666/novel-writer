# Copyright (c) 2025 ByteDance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""OpenAI API client wrapper with tool integration."""

import json
from typing import override

import openai
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionAssistantMessageParam,
    ChatCompletionFunctionMessageParam,
    ChatCompletionMessageParam,
    ChatCompletionMessageToolCallParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionToolParam,
    ChatCompletionUserMessageParam,
)
from openai.types.chat.chat_completion_message_tool_call_param import Function
from openai.types.chat.chat_completion_tool_message_param import (
    ChatCompletionToolMessageParam,
)
from openai.types.shared_params.function_definition import FunctionDefinition

from trae_agent.tools.base import Tool, ToolCall, ToolResult
from trae_agent.utils.config import ModelConfig
from trae_agent.utils.llm_clients.base_client import BaseLLMClient
from trae_agent.utils.llm_clients.llm_basics import LLMMessage, LLMResponse, LLMUsage
from trae_agent.utils.llm_clients.retry_utils import retry_with


class OpenAIClient(BaseLLMClient):
    """OpenAI client wrapper with tool schema generation."""

    def __init__(self, model_config: ModelConfig):
        super().__init__(model_config)

        self.client: openai.OpenAI = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)
        self.message_history: list[ChatCompletionMessageParam] = []

    @override
    def set_chat_history(self, messages: list[LLMMessage]) -> None:
        """Set the chat history."""
        self.message_history = self.parse_messages(messages)

    def _create_openai_response(
        self,
        messages: list[ChatCompletionMessageParam],
        model_config: ModelConfig,
        tool_schemas: list[ChatCompletionToolParam] | None,
    ) -> ChatCompletion:
        """Create a response using OpenAI API. This method will be decorated with retry logic."""
        token_params = {}
        if model_config.should_use_max_completion_tokens():
            token_params["max_completion_tokens"] = model_config.get_max_tokens_param()
        else:
            token_params["max_tokens"] = model_config.get_max_tokens_param()
            
        return self.client.chat.completions.create(
            model=model_config.model,
            messages=messages,
            tools=tool_schemas if tool_schemas else openai.NOT_GIVEN,
            temperature=model_config.temperature
            if "o3" not in model_config.model
            and "o4-mini" not in model_config.model
            and "gpt-5" not in model_config.model
            else openai.NOT_GIVEN,
            top_p=model_config.top_p,
            **token_params,
        )

    @override
    def chat(
        self,
        messages: list[LLMMessage],
        model_config: ModelConfig,
        tools: list[Tool] | None = None,
        reuse_history: bool = True,
    ) -> LLMResponse:
        """Send chat messages to OpenAI with optional tool support."""
        parsed_messages = self.parse_messages(messages)
        if reuse_history:
            self.message_history = self.message_history + parsed_messages
        else:
            self.message_history = parsed_messages

        tool_schemas = None
        if tools:
            tool_schemas = [
                ChatCompletionToolParam(
                    function=FunctionDefinition(
                        name=tool.get_name(),
                        description=tool.get_description(),
                        parameters=tool.get_input_schema(),
                    ),
                    type="function",
                )
                for tool in tools
            ]

        # Apply retry decorator to the API call
        retry_decorator = retry_with(
            func=self._create_openai_response,
            provider_name="OpenAI",
            max_retries=model_config.max_retries,
        )
        response = retry_decorator(self.message_history, model_config, tool_schemas)

        choice = response.choices[0]
        content = choice.message.content or ""
        tool_calls: list[ToolCall] = []
        
        if choice.message.tool_calls:
            for tool_call in choice.message.tool_calls:
                tool_calls.append(
                    ToolCall(
                        call_id=tool_call.id,
                        name=tool_call.function.name,
                        arguments=json.loads(tool_call.function.arguments)
                        if tool_call.function.arguments
                        else {},
                        id=tool_call.id,
                    )
                )

        # Update message history with assistant response
        if tool_calls:
            self.message_history.append(
                ChatCompletionAssistantMessageParam(
                    content=content,
                    role="assistant",
                    tool_calls=[
                        ChatCompletionMessageToolCallParam(
                            id=tc.call_id,
                            function=Function(
                                name=tc.name,
                                arguments=json.dumps(tc.arguments),
                            ),
                            type="function",
                        )
                        for tc in tool_calls
                    ],
                )
            )
        elif content:
            self.message_history.append(
                ChatCompletionAssistantMessageParam(content=content, role="assistant")
            )

        usage = None
        if response.usage:
            usage = LLMUsage(
                input_tokens=response.usage.prompt_tokens or 0,
                output_tokens=response.usage.completion_tokens or 0,
                cache_read_input_tokens=getattr(getattr(response.usage, "prompt_tokens_details", None), "cached_tokens", 0) if hasattr(response.usage, "prompt_tokens_details") else 0,
                reasoning_tokens=getattr(getattr(response.usage, "completion_tokens_details", None), "reasoning_tokens", 0) if hasattr(response.usage, "completion_tokens_details") else 0,
            )

        llm_response = LLMResponse(
            content=content,
            usage=usage,
            model=response.model,
            finish_reason=choice.finish_reason,
            tool_calls=tool_calls if len(tool_calls) > 0 else None,
        )

        # Record trajectory if recorder is available
        if self.trajectory_recorder:
            self.trajectory_recorder.record_llm_interaction(
                messages=messages,
                response=llm_response,
                provider="openai",
                model=model_config.model,
                tools=tools,
            )

        return llm_response

    def parse_messages(self, messages: list[LLMMessage]) -> list[ChatCompletionMessageParam]:
        """Parse the messages to OpenAI ChatCompletion format."""
        openai_messages: list[ChatCompletionMessageParam] = []
        for msg in messages:
            if msg.tool_result:
                openai_messages.append(self.parse_tool_call_result(msg.tool_result))
            elif msg.tool_call:
                # Tool calls are handled differently - they should be part of assistant messages
                # This case shouldn't normally occur in isolation
                pass
            else:
                if not msg.content:
                    raise ValueError("Message content is required")
                if msg.role == "system":
                    openai_messages.append(ChatCompletionSystemMessageParam(role="system", content=msg.content))
                elif msg.role == "user":
                    openai_messages.append(ChatCompletionUserMessageParam(role="user", content=msg.content))
                elif msg.role == "assistant":
                    openai_messages.append(ChatCompletionAssistantMessageParam(role="assistant", content=msg.content))
                else:
                    raise ValueError(f"Invalid message role: {msg.role}")
        return openai_messages

    def parse_tool_call_result(self, tool_call_result: ToolResult) -> ChatCompletionToolMessageParam:
        """Parse the tool call result to ChatCompletion tool message format."""
        result_content: str = ""
        if tool_call_result.result is not None:
            result_content += str(tool_call_result.result)
        if tool_call_result.error:
            result_content += f"\nError: {tool_call_result.error}"
        result_content = result_content.strip()

        return ChatCompletionToolMessageParam(
            role="tool",
            content=result_content,
            tool_call_id=tool_call_result.call_id,
        )
