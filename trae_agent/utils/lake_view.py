import re
from dataclasses import dataclass

from trae_agent.agent.agent_basics import AgentStep
from trae_agent.utils.config import LakeviewConfig
from trae_agent.utils.llm_clients.llm_basics import LLMMessage
from trae_agent.utils.llm_clients.llm_client import LLMClient

StepType = tuple[
    str,  # content for human (will write into result file)
    str
    | None,  # content for llm, or None if no need to analyze (i.e., minor step), watch out length limit
]


EXTRACTOR_PROMPT = """
根据前面的摘录，你的任务是确定"代理在<this_step>中正在执行什么任务"。
请用两个层次输出你的答案：<task>...</task><details>...</details>。
在<task>标签中，答案应该简洁而概括。它应该省略任何特定于bug的细节，最多包含10个词。
在<details>标签中，答案应该通过添加特定于bug的细节来补充<task>标签。它应该是信息丰富的，最多包含30个词。

示例：

<task>代理正在编写复现测试脚本。</task><details>代理正在编写"test_bug.py"来复现XXX-Project的create_foo方法未正确比较大小的bug。</details>
<task>代理正在检查源代码。</task><details>代理正在代码仓库中搜索"function_name"，这与堆栈跟踪中的"foo.py:function_name"行相关。</details>
<task>代理正在修复复现测试脚本。</task><details>代理正在修复"test_bug.py"，该脚本忘记导入函数"foo"，导致NameError。</details>

现在，回答问题"代理在<this_step>中正在执行什么任务"。
再次强调，只提供答案，不要其他评论。格式应该是"<task>...</task><details>...</details>"。
"""

TAGGER_PROMPT = """
根据轨迹，你的任务是确定"代理在当前步骤中正在执行什么任务"。
通过从下面的列表中选择适用于当前步骤的标签来输出你的答案。
如果它在一个步骤中执行多个任务，请选择所有适用的标签，用逗号分隔。

<tags>
WRITE_TEST: 它编写测试脚本来复现bug，或修改无法工作的测试脚本以修复测试中发现的问题。
VERIFY_TEST: 它运行复现测试脚本来验证测试环境是否正常工作。
EXAMINE_CODE: 它查看、搜索或探索代码仓库以了解bug的原因。
WRITE_FIX: 它修改源代码以修复已识别的bug。
VERIFY_FIX: 它运行复现测试或现有测试来验证修复确实解决了bug。
REPORT: 它向用户报告工作已完成或取得了一些进展。
THINK: 它通过思考分析bug，但目前不执行具体行动。
OUTLIER: 此步骤的主要部分不符合上述任何标签，例如运行shell命令安装依赖项。
</tags>

<examples>
如果代理正在打开文件进行检查，输出<tags>EXAMINE_CODE</tags>。
如果代理正在修复复现测试脚本中的已知问题然后再次运行它，输出<tags>WRITE_TEST,VERIFY_TEST</tags>。
如果代理仅仅在思考bug的根本原因而没有其他行动，输出<tags>THINK</tags>。
</examples>

只输出标签，不要其他评论。格式应该是<tags>...</tags>
"""

KNOWN_TAGS = {
    "WRITE_TEST": "☑️",
    "VERIFY_TEST": "✅",
    "EXAMINE_CODE": "👁️",
    "WRITE_FIX": "📝",
    "VERIFY_FIX": "🔥",
    "REPORT": "📣",
    "THINK": "🧠",
    "OUTLIER": "⁉️",
}

tags_re = re.compile(r"<tags>([A-Z_,\s]+)</tags>")


@dataclass
class LakeViewStep:
    desc_task: str
    desc_details: str
    tags_emoji: str


class LakeView:
    def __init__(self, lake_view_config: LakeviewConfig | None):
        if lake_view_config is None:
            return

        self.model_config = lake_view_config.model
        self.lakeview_llm_client: LLMClient = LLMClient(self.model_config)

        self.steps: list[str] = []

    def get_label(self, tags: None | list[str], emoji: bool = True) -> str:
        if not tags:
            return ""

        return " · ".join([KNOWN_TAGS[tag] + tag if emoji else tag for tag in tags])

    async def extract_task_in_step(self, prev_step: str, this_step: str) -> tuple[str, str]:
        llm_messages = [
            LLMMessage(
                role="user",
                content=f"The following is an excerpt of the steps trying to solve a software bug by an AI agent: <previous_step>{prev_step}</previous_step><this_step>{this_step}</this_step>",
            ),
            LLMMessage(role="assistant", content="I understand."),
            LLMMessage(role="user", content=EXTRACTOR_PROMPT),
            LLMMessage(
                role="assistant",
                content="Sure. Here is the task the agent is performing: <task>The agent",
            ),
        ]

        self.model_config.temperature = 0.1
        llm_response = self.lakeview_llm_client.chat(
            model_config=self.model_config,
            messages=llm_messages,
            reuse_history=False,
        )

        content = llm_response.content.strip()

        retry = 0
        while retry < 10 and (
            "</task>" not in content or "<details>" not in content or "</details>" not in content
        ):
            retry += 1
            llm_response = self.lakeview_llm_client.chat(
                model_config=self.model_config,
                messages=llm_messages,
                reuse_history=False,
            )
            content = llm_response.content.strip()

        if "</task>" not in content or "<details>" not in content or "</details>" not in content:
            return "", ""

        desc_task, _, desc_details = content.rpartition("</task>")
        desc_details = desc_details.replace("<details>", "[italic]").replace(
            "</details>", "[/italic]"
        )
        return desc_task, desc_details

    async def extract_tag_in_step(self, step: str) -> list[str]:
        steps_fmt = "\n\n".join(
            f'<step id="{ind + 1}">\n{s.strip()}\n</step>' for ind, s in enumerate(self.steps)
        )

        if len(steps_fmt) > 300_000:
            # step_fmt is too long, skip tagging
            return []

        llm_messages = [
            LLMMessage(
                role="user",
                content=f"Below is the trajectory of an AI agent solving a software bug until the current step. Each step is marked within a <step> tag.\n\n{steps_fmt}\n\n<current_step>{step}</current_step>",
            ),
            LLMMessage(role="assistant", content="I understand."),
            LLMMessage(role="user", content=TAGGER_PROMPT),
            LLMMessage(role="assistant", content="Sure. The tags are: <tags>"),
        ]
        self.model_config.temperature = 0.1

        retry = 0
        while retry < 10:
            llm_response = self.lakeview_llm_client.chat(
                model_config=self.model_config,
                messages=llm_messages,
                reuse_history=False,
            )

            content = "<tags>" + llm_response.content.lstrip()

            matched_tags: list[str] = tags_re.findall(content)
            if not matched_tags:
                break
            tags: list[str] = [tag.strip() for tag in matched_tags[0].split(",")]
            if all(tag in KNOWN_TAGS for tag in tags):
                return tags

            retry += 1

        return []

    def _agent_step_str(self, agent_step: AgentStep) -> str | None:
        if agent_step.llm_response is None:
            return None

        content = agent_step.llm_response.content.strip()

        tool_calls_content = ""
        if agent_step.llm_response.tool_calls is not None:
            tool_calls_content = "\n".join(
                f"[`{tool_call.name}`] `{tool_call.arguments}`"
                for tool_call in agent_step.llm_response.tool_calls
            )
            tool_calls_content = tool_calls_content.strip()
            content = f"{content}\n\nTool calls:\n{tool_calls_content}"

        return content

    async def create_lakeview_step(self, agent_step: AgentStep) -> LakeViewStep | None:
        previous_step_str = "(none)"
        if len(self.steps) > 1:
            previous_step_str = self.steps[-1]

        this_step_str = self._agent_step_str(agent_step)

        if this_step_str:
            desc_task, desc_details = await self.extract_task_in_step(
                previous_step_str, this_step_str
            )
            tags = await self.extract_tag_in_step(this_step_str)
            tags_emoji = self.get_label(tags)
            return LakeViewStep(desc_task, desc_details, tags_emoji)

        return None
