from anthropic.types import ToolParam

TRIAGE_SYSTEM_PROMPT = """你是任务分流器。根据用户消息判断处理方式。

如果是知识问答、概念解释、翻译、简单代码展示、闲聊、方案讨论、数学计算等不需要文件系统操作的任务，直接用markdown格式回答。

如果需要编程CLI工具（读写文件、修改代码、运行命令、git操作、项目构建、访问文件系统），调用对应的工具：
- call_claude: 复杂代码架构、代码审查、安全分析、长文档、复杂推理、多步骤规划
"""

_INPUT_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "task": {
            "type": "string",
            "description": "需要处理的任务描述",
        }
    },
    "required": ["task"],
}

TRIAGE_TOOLS: list[ToolParam] = [
    {
        "name": "call_claude",
        "description": "将任务转发给Claude CLI处理。适用于复杂代码架构、代码审查、安全分析、长文档、复杂推理、多步骤规划等任务。",
        "input_schema": _INPUT_SCHEMA
    }
]

TOOL_NAME_TO_CLIENT = {
    "call_claude": "claude",
    "call_codex": "codex",
    "call_gemini": "gemini",
}
