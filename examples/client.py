"""
示例客户端
"""

import httpx


def chat(prompt: str, session_id: str | None = None, cwd: str = ".") -> dict:
    """发送消息并获取完整响应"""
    response = httpx.post(
        "http://localhost:8000/api/v1/chat",
        json={"prompt": prompt, "session_id": session_id, "cwd": cwd},
        timeout=600,
    )
    response.raise_for_status()
    return response.json()


def chat_stream(prompt: str, session_id: str | None = None, cwd: str = "."):
    """流式发送消息"""
    with httpx.stream(
        "POST",
        "http://localhost:8000/api/v1/chat/stream",
        json={"prompt": prompt, "session_id": session_id, "cwd": cwd},
        timeout=600,
    ) as response:
        for line in response.iter_lines():
            if line.startswith("data: "):
                data = line[6:]
                if data == "[DONE]":
                    break
                yield data


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage: python client.py <prompt> [cwd]")
        sys.exit(1)

    prompt = sys.argv[1]
    cwd = sys.argv[2] if len(sys.argv) > 2 else "."

    print(f"Prompt: {prompt}")
    print(f"CWD: {cwd}")
    print("-" * 40)

    for chunk in chat_stream(prompt, cwd=cwd):
        try:
            data = json.loads(chunk)
            if data["type"] == "message_delta":
                print(data["data"]["text"], end="", flush=True)
            elif data["type"] == "tool_call":
                print(f"\n[Tool: {data['data']['tool_name']}]", flush=True)
        except json.JSONDecodeError:
            pass

    print()
