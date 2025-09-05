# Copyright (c) 2025 ByteDance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import os
from typing import override

from trae_agent.tools.base import Tool, ToolCallArguments, ToolError, ToolExecResult, ToolParameter


class SaveFileTool(Tool):
    """
    允许代理将内容保存到文件的工具。
    支持追加和覆盖两种模式。
    """

    def __init__(self, model_provider: str | None = None):
        super().__init__(model_provider)

    @override
    def get_model_provider(self) -> str | None:
        return self._model_provider

    @override
    def get_name(self) -> str:
        return "save_file"

    @override
    def get_description(self) -> str:
        return """使用指定的写入模式将内容保存到文件。
* 支持追加（'a'）和覆盖（'w'）两种模式。
* 如果目录不存在会自动创建。
* 文件路径应为绝对路径。
"""

    @override
    def get_parameters(self) -> list[ToolParameter]:
        # 对于 OpenAI 模型，所有参数必须设置 required=True
        # 对于其他提供商，可选参数可以设置 required=False
        mode_required = self.model_provider == "openai"

        return [
            ToolParameter(
                name="filename",
                type="string",
                description="要保存的文件绝对路径。",
                required=True,
            ),
            ToolParameter(
                name="content",
                type="string",
                description="要写入文件的内容。",
                required=True,
            ),
            ToolParameter(
                name="mode",
                type="string",
                description="写入模式：'a' 表示追加，在原有内容后追加；'w' 表示覆盖，将原有内容全部删除后再写入。默认为 'w'。",
                required=mode_required,
            ),
        ]

    @override
    async def execute(self, arguments: ToolCallArguments) -> ToolExecResult:
        try:
            filename = str(arguments.get("filename", ""))
            content = str(arguments.get("content", ""))
            mode = str(arguments.get("mode", "w"))

            if not filename:
                return ToolExecResult(
                    error="文件名是必需的",
                    error_code=-1,
                )

            if mode not in ["a", "w"]:
                return ToolExecResult(
                    error="模式必须是 'a'（追加）或 'w'（覆盖）",
                    error_code=-1,
                )

            # 如果目录不存在则创建目录
            directory = os.path.dirname(filename)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)

            # 将内容写入文件
            with open(filename, mode, encoding="utf-8") as f:
                f.write(content)

            action = "追加到" if mode == "a" else "写入到"
            return ToolExecResult(
                output=f"内容成功{action} '{filename}' （{len(content)} 个字符）"
            )

        except FileNotFoundError as e:
            return ToolExecResult(
                error=f"文件未找到: {e}",
                error_code=-1,
            )
        except PermissionError as e:
            return ToolExecResult(
                error=f"权限被拒绝: {e}",
                error_code=-1,
            )
        except Exception as e:
            return ToolExecResult(
                error=f"保存文件时出错: {e}",
                error_code=-1,
            )

    @override
    async def close(self):
        """文件操作无需清理资源。"""
        pass