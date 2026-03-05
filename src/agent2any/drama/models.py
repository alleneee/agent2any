import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any


def safe_parse_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        start = 1 if lines[0].startswith("```") else 0
        end = len(lines)
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip() == "```":
                end = i
                break
        text = "\n".join(lines[start:end])

    json_match = re.search(r"[\[\{].*[\]\}]", text, re.DOTALL)
    if json_match:
        text = json_match.group()

    return json.loads(text)


@dataclass
class DramaProject:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    theme: str = ""
    genre: str = ""
    outline: dict = field(default_factory=dict)
    episodes: list[dict] = field(default_factory=list)
    characters: list[dict] = field(default_factory=list)
    scenes: list[dict] = field(default_factory=list)
    props: list[dict] = field(default_factory=list)
    storyboards: dict[int, list[dict]] = field(default_factory=dict)


@dataclass
class WorkflowStep:
    name: str
    status: str = "pending"
    progress: int = 0
    message: str = ""
    result: Any = None
