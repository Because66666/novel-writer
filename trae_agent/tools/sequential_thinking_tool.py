# Copyright (c) 2023 Anthropic
# Copyright (c) 2025 ByteDance Ltd. and/or its affiliates.
# SPDX-License-Identifier: MIT
#
# This file has been modified by ByteDance Ltd. and/or its affiliates. on 13 June 2025
#
# Original file was released under MIT License, with the full license text
# available at https://github.com/anthropics/anthropic-quickstarts/blob/main/LICENSE
#
# This modified file is released under the same license.

import json
from dataclasses import dataclass
from typing import override

from trae_agent.tools.base import Tool, ToolCallArguments, ToolExecResult, ToolParameter


@dataclass
class ThoughtData:
    thought: str
    thought_number: int
    total_thoughts: int
    next_thought_needed: bool
    is_revision: bool | None = None
    revises_thought: int | None = None
    branch_from_thought: int | None = None
    branch_id: str | None = None
    needs_more_thoughts: bool | None = None


class SequentialThinkingTool(Tool):
    """用于顺序思考的工具，帮助分解复杂问题。

    该工具通过灵活的思考过程帮助分析问题，可以适应和演进。
    每个思考步骤都可以基于、质疑或修正之前的见解，随着理解的深入而发展。
    """

    @override
    def get_name(self) -> str:
        return "sequentialthinking"

    @override
    def get_description(self) -> str:
        return """通过思考进行动态和反思性问题解决的详细工具。
该工具通过灵活的思考过程帮助分析问题，可以适应和演进。
每个思考步骤都可以基于、质疑或修正之前的见解，随着理解的深入而发展。

何时使用此工具：
- 将复杂问题分解为步骤
- 需要修正空间的规划和设计
- 可能需要纠正方向的分析
- 初始阶段全貌不清晰的问题
- 需要多步骤解决方案的问题
- 需要在多个步骤中保持上下文的任务
- 需要过滤无关信息的情况

主要特性：
- 可以在进展过程中向上或向下调整总思考数
- 可以质疑或修正之前的思考
- 即使在看似结束后也可以添加更多思考
- 可以表达不确定性并探索替代方法
- 不是每个思考都需要线性构建 - 可以分支或回溯
- 生成解决方案假设
- 基于思维链步骤验证假设
- 重复过程直到满意
- 提供正确答案

参数说明：
- thought: 当前思考步骤，可以包括：
* 常规分析步骤
* 对之前思考的修正
* 对之前决策的质疑
* 意识到需要更多分析
* 方法的改变
* 假设生成
* 假设验证
- next_thought_needed: 如果需要更多思考则为True，即使在看似结束时
- thought_number: 序列中的当前编号（如需要可超过初始总数）
- total_thoughts: 当前估计需要的思考数（可向上/向下调整）
- is_revision: 布尔值，指示此思考是否修正之前的思考
- revises_thought: 如果is_revision为true，指示正在重新考虑的思考编号
- branch_from_thought: 如果分支，指示分支点的思考编号
- branch_id: 当前分支的标识符（如果有）
- needs_more_thoughts: 如果到达结尾但意识到需要更多思考

你应该：
1. 从所需思考的初始估计开始，但准备好调整
2. 随时质疑或修正之前的思考
3. 如果需要，不要犹豫添加更多思考，即使在"结尾"
4. 在存在时表达不确定性
5. 标记修正之前思考或分支到新路径的思考
6. 忽略与当前步骤无关的信息
7. 在适当时生成解决方案假设
8. 基于思维链步骤验证假设
9. 重复过程直到对解决方案满意
10. 提供单一的、理想情况下正确的答案作为最终输出
11. 只有在真正完成并达到满意答案时才将next_thought_needed设为false"""

    @override
    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="thought",
                type="string",
                description="当前思考步骤",
                required=True,
            ),
            ToolParameter(
                name="next_thought_needed",
                type="boolean",
                description="是否需要另一个思考步骤",
                required=True,
            ),
            ToolParameter(
                name="thought_number",
                type="integer",
                description="当前思考编号。最小值为1。",
                required=True,
            ),
            ToolParameter(
                name="total_thoughts",
                type="integer",
                description="估计需要的总思考数。最小值为1。",
                required=True,
            ),
            ToolParameter(
                name="is_revision",
                type="boolean",
                description="是否修正之前的思考",
            ),
            ToolParameter(
                name="revises_thought",
                type="integer",
                description="正在重新考虑的思考编号。最小值为1。",
            ),
            ToolParameter(
                name="branch_from_thought",
                type="integer",
                description="分支点思考编号。最小值为1。",
            ),
            ToolParameter(
                name="branch_id",
                type="string",
                description="分支标识符",
            ),
            ToolParameter(
                name="needs_more_thoughts",
                type="boolean",
                description="是否需要更多思考",
            ),
        ]

    def __init__(self, model_provider: str | None = None) -> None:
        super().__init__(model_provider)
        self.thought_history: list[ThoughtData] = []
        self.branches: dict[str, list[ThoughtData]] = {}

    @override
    def get_model_provider(self) -> str | None:
        return self._model_provider

    def _validate_thought_data(self, arguments: ToolCallArguments) -> ThoughtData:
        """验证输入参数并返回ThoughtData对象。"""
        if "thought" not in arguments or not isinstance(arguments["thought"], str):
            raise ValueError("无效的思考：必须是字符串")

        if "thought_number" not in arguments or not isinstance(arguments["thought_number"], int):
            raise ValueError("无效的思考编号：必须是数字")

        if "total_thoughts" not in arguments or not isinstance(arguments["total_thoughts"], int):
            raise ValueError("无效的总思考数：必须是数字")

        if "next_thought_needed" not in arguments or not isinstance(
            arguments["next_thought_needed"], bool
        ):
            raise ValueError("无效的next_thought_needed：必须是布尔值")

        # 验证最小值
        if arguments["thought_number"] < 1:
            raise ValueError("思考编号必须至少为1")

        if arguments["total_thoughts"] < 1:
            raise ValueError("总思考数必须至少为1")

        # 验证可选的修正字段
        if (
            "revises_thought" in arguments
            and arguments["revises_thought"] is not None
            and arguments["revises_thought"] != 0
        ):
            if (
                not isinstance(arguments["revises_thought"], int)
                or arguments["revises_thought"] < 1
            ):
                raise ValueError("修正思考编号必须是正整数")
            else:
                revises_thought = int(arguments["revises_thought"])
        else:
            revises_thought = None

        if (
            "branch_from_thought" in arguments
            and arguments["branch_from_thought"] is not None
            and arguments["branch_from_thought"] != 0
        ):
            if (
                not isinstance(arguments["branch_from_thought"], int)
                or arguments["branch_from_thought"] < 1
            ):
                raise ValueError("分支起始思考编号必须是正整数")
            else:
                branch_from_thought = int(arguments["branch_from_thought"])
        else:
            branch_from_thought = None

        # 提取并转换验证后的值
        thought = str(arguments["thought"])
        thought_number = int(arguments["thought_number"])  # Already validated as int
        total_thoughts = int(arguments["total_thoughts"])  # Already validated as int
        next_thought_needed = bool(arguments["next_thought_needed"])  # Already validated as bool

        # 处理可选字段并进行适当的类型检查
        is_revision = None
        branch_id = None
        needs_more_thoughts = None

        if "is_revision" in arguments and arguments["is_revision"] is not None:
            is_revision = bool(arguments["is_revision"])

        if "branch_id" in arguments and arguments["branch_id"] is not None:
            branch_id = str(arguments["branch_id"])

        if "needs_more_thoughts" in arguments and arguments["needs_more_thoughts"] is not None:
            needs_more_thoughts = bool(arguments["needs_more_thoughts"])

        return ThoughtData(
            thought=thought,
            thought_number=thought_number,
            total_thoughts=total_thoughts,
            next_thought_needed=next_thought_needed,
            is_revision=is_revision,
            revises_thought=revises_thought,
            branch_from_thought=branch_from_thought,
            branch_id=branch_id,
            needs_more_thoughts=needs_more_thoughts,
        )

    def _format_thought(self, thought_data: ThoughtData) -> str:
        """格式化思考以供显示，带有视觉样式。"""
        prefix = ""
        context = ""

        if thought_data.is_revision:
            prefix = "🔄 修正"
            context = f" (修正思考 {thought_data.revises_thought})"
        elif thought_data.branch_from_thought:
            prefix = "🌿 分支"
            context = (
                f" (从思考 {thought_data.branch_from_thought}, ID: {thought_data.branch_id})"
            )
        else:
            prefix = "💭 思考"
            context = ""

        header = f"{prefix} {thought_data.thought_number}/{thought_data.total_thoughts}{context}"
        border_length = max(len(header), len(thought_data.thought)) + 4
        border = "─" * border_length

        return f"""
┌{border}┐
│ {header.ljust(border_length - 2)} │
├{border}┤
│ {thought_data.thought.ljust(border_length - 2)} │
└{border}┘"""

    @override
    async def execute(self, arguments: ToolCallArguments) -> ToolExecResult:
        """执行顺序思考工具。"""
        try:
            # 验证并提取思考数据
            validated_input = self._validate_thought_data(arguments)

            # 如果当前思考编号超过总数，则调整总思考数
            if validated_input.thought_number > validated_input.total_thoughts:
                validated_input.total_thoughts = validated_input.thought_number

            # 添加到思考历史
            self.thought_history.append(validated_input)

            # 处理分支
            if validated_input.branch_from_thought and validated_input.branch_id:
                if validated_input.branch_id not in self.branches:
                    self.branches[validated_input.branch_id] = []
                self.branches[validated_input.branch_id].append(validated_input)

            # 格式化并显示思考
            # formatted_thought = self._format_thought(validated_input)
            # print(formatted_thought, flush=True)  # 打印到标准输出以获得即时反馈

            # 准备响应
            response_data = {
                "thought_number": validated_input.thought_number,
                "total_thoughts": validated_input.total_thoughts,
                "next_thought_needed": validated_input.next_thought_needed,
                "branches": list(self.branches.keys()),
                "thought_history_length": len(self.thought_history),
            }

            return ToolExecResult(
                output=f"顺序思考步骤已完成。\n\n状态：\n{json.dumps(response_data, indent=2)}"
            )

        except Exception as e:
            error_data = {"error": str(e), "status": "failed"}
            return ToolExecResult(
                error=f"顺序思考失败：{str(e)}\n\n详情：\n{json.dumps(error_data, indent=2)}",
                error_code=-1,
            )
