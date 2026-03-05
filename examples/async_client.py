"""
异步客户端示例
"""

import asyncio
import json

import httpx


async def chat(prompt: str, session_id: str | None = None, cwd: str = ".") -> dict:
    """发送消息并获取完整响应"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/chat",
            json={"prompt": prompt, "session_id": session_id, "cwd": cwd},
            timeout=600,
        )
        response.raise_for_status()
        return response.json()


async def chat_stream(prompt: str, session_id: str | None = None, cwd: str = "."):
    """流式发送消息"""
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            "http://localhost:8000/api/v1/chat/stream",
            json={"prompt": prompt, "session_id": session_id, "cwd": cwd},
            timeout=600,
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    yield data


async def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: python async_client.py <prompt> [cwd]")
        sys.exit(1)

    prompt = sys.argv[1]
    cwd = sys.argv[2] if len(sys.argv) > 2 else "."

    print(f"Prompt: {prompt}")
    print(f"CWD: {cwd}")
    print("-" * 40)

    session_id = None

    async for chunk in chat_stream(prompt, session_id=session_id, cwd=cwd):
        try:
            data = json.loads(chunk)
            if data["type"] == "session":
                session_id = data["data"]["session_id"]
            elif data["type"] == "message_delta":
                print(data["data"]["text"], end="", flush=True)
            elif data["type"] == "tool_call":
                tool = data["data"]
                print(f"\n[Tool: {tool['tool_name']} - {tool['status']}]", flush=True)
        except json.JSONDecodeError:
            pass

    print()
    print("-" * 40)
    print(f"Session ID: {session_id}")


if __name__ == "__main__":
    asyncio.run(main())
