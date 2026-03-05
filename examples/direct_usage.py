"""
直接使用 ClaudeAgent（不需要 HTTP 服务）
"""

import asyncio
import sys

sys.path.insert(0, str(__file__).rsplit("/", 2)[0] + "/src")

from agent2any.agent import ClaudeAgent, MessageDelta, ToolCall


async def main():
    if len(sys.argv) < 2:
        print("Usage: python direct_usage.py <prompt> [cwd]")
        sys.exit(1)

    prompt = sys.argv[1]
    cwd = sys.argv[2] if len(sys.argv) > 2 else "."

    print(f"Prompt: {prompt}")
    print(f"CWD: {cwd}")
    print("-" * 40)

    agent = ClaudeAgent(cwd=cwd)

    try:
        async for event in agent.send_prompt_stream(prompt):
            if isinstance(event, MessageDelta):
                if event.msg_type == "message_delta":
                    print(event.text, end="", flush=True)
                elif event.msg_type == "reasoning_delta":
                    print(f"[思考: {event.text}]", end="", flush=True)
            elif isinstance(event, ToolCall):
                print(f"\n[工具调用: {event.tool_name} - {event.status}]", flush=True)
            elif isinstance(event, dict):
                event_type = event.get("type", "")
                if event_type == "turn_complete":
                    print("\n[完成]")

        print()
        print("-" * 40)
        print(f"Session ID: {agent.session_id}")

    finally:
        await agent.stop()


if __name__ == "__main__":
    asyncio.run(main())
