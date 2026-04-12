import json
import re
from langchain_core.messages import AIMessage

# Matches the inner content of an optional ```json ... ``` or ``` ... ``` fence
_FENCE_RE = re.compile(r'```(?:json)?\s*(.*?)\s*```', re.DOTALL)
# Matches individual top-level JSON objects anywhere in a string
_OBJECT_RE = re.compile(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}', re.DOTALL)

def _unwrap_fences(content: str) -> str:
    """Strip markdown code fences if present, otherwise return content as-is."""
    if match := _FENCE_RE.search(content):
        return match.group(1)
    return content.strip()

def _parse_tool_calls(text: str) -> list[dict]:
    """Extract all valid tool-call JSON objects from text."""
    tool_calls = []
    for i, match in enumerate(_OBJECT_RE.finditer(text)):
        try:
            data = json.loads(match.group())
            name = data.get('name')
            args = data.get('arguments') or data.get('args') or {}
            if name and isinstance(args, dict):
                tool_calls.append({'name': name, 'args': args, 'id': f'coerced_{i}', 'type': 'tool_call'})
        except (json.JSONDecodeError, AttributeError):
            continue
    return tool_calls

def _extract_text(content) -> str:
    """Normalize content to a plain string, handling Gemini's list-of-blocks format."""
    if isinstance(content, list):
        return '\n'.join(block.get('text', '') for block in content if isinstance(block, dict) and block.get('type') == 'text')
    return content

def coerce_tool_calls(ai_message: AIMessage) -> AIMessage:
    """If tool_calls is empty but content contains JSON tool calls (bare or fenced,
    single or multiple), synthesize the tool call list."""
    if ai_message.tool_calls or not ai_message.content:
        return ai_message
    tool_calls = _parse_tool_calls(_unwrap_fences(_extract_text(ai_message.content)))
    if tool_calls:
        return AIMessage(content='', tool_calls=tool_calls)
    return ai_message
