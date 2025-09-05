# Copyright (c) 2025 ByteDance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import os
from typing import override

from trae_agent.tools.base import Tool, ToolCallArguments, ToolError, ToolExecResult, ToolParameter


class ReadFileTool(Tool):
    """
    允许代理从文件中读取内容的工具。
    支持读取整个文件或指定行数范围。
    """

    def __init__(self, model_provider: str | None = None):
        super().__init__(model_provider)

    @override
    def get_model_provider(self) -> str | None:
        return self._model_provider

    @override
    def get_name(self) -> str:
        return "read_file"

    @override
    def get_description(self) -> str:
        return """从文件中读取内容。
* 支持读取整个文件或指定行数范围。
* 文件路径应为绝对路径。
* 自动处理文件编码。
"""

    @override
    def get_parameters(self) -> list[ToolParameter]:
        # 对于 OpenAI 模型，所有参数必须设置 required=True
        # 对于其他提供商，可选参数可以设置 required=False
        optional_required = self.model_provider == "openai"

        return [
            ToolParameter(
                name="filename",
                type="string",
                description="要读取的文件绝对路径。",
                required=True,
            ),
            ToolParameter(
                name="start_line",
                type="integer",
                description="开始读取的行号（从1开始）。如果不指定，则从第一行开始。",
                required=optional_required,
            ),
            ToolParameter(
                name="end_line",
                type="integer",
                description="结束读取的行号（包含该行）。如果不指定，则读取到文件末尾。",
                required=optional_required,
            ),
        ]

    @override
    async def execute(self, arguments: ToolCallArguments) -> ToolExecResult:
        try:
            filename = str(arguments.get("filename", ""))
            start_line = arguments.get("start_line")
            end_line = arguments.get("end_line")

            if not filename:
                return ToolExecResult(
                    error="文件名是必需的",
                    error_code=-1,
                )

            if not os.path.exists(filename):
                return ToolExecResult(
                    error=f"文件不存在: {filename}",
                    error_code=-1,
                )

            # 读取文件内容
            with open(filename, "r", encoding="utf-8") as f:
                if start_line is not None or end_line is not None:
                    # 按行读取
                    lines = f.readlines()
                    total_lines = len(lines)
                    
                    # 处理行号参数
                    start_idx = (int(start_line) - 1) if start_line is not None else 0
                    end_idx = int(end_line) if end_line is not None else total_lines
                    
                    # 验证行号范围
                    if start_idx < 0:
                        start_idx = 0
                    if end_idx > total_lines:
                        end_idx = total_lines
                    if start_idx >= end_idx:
                        return ToolExecResult(
                            error="开始行号必须小于结束行号",
                            error_code=-1,
                        )
                    
                    # 提取指定范围的行
                    selected_lines = lines[start_idx:end_idx]
                    content = "".join(selected_lines)
                    
                    return ToolExecResult(
                        output=f"成功读取 '{filename}' 第 {start_idx + 1}-{end_idx} 行 （{len(selected_lines)} 行，{len(content)} 个字符）\n\n{content}"
                    )
                else:
                    # 读取整个文件
                    content = f.read()
                    line_count = content.count('\n') + 1 if content else 0
                    
                    return ToolExecResult(
                        output=f"成功读取 '{filename}' （{line_count} 行，{len(content)} 个字符）\n\n{content}"
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
        except UnicodeDecodeError as e:
            return ToolExecResult(
                error=f"文件编码错误，无法读取: {e}",
                error_code=-1,
            )
        except Exception as e:
            return ToolExecResult(
                error=f"读取文件时出错: {e}",
                error_code=-1,
            )

    @override
    async def close(self):
        """文件操作无需清理资源。"""
        pass