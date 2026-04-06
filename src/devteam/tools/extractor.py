import json
from langchain_core.messages import AIMessage

def coerce_tool_calls(ai_message: AIMessage) -> AIMessage:
    """If tool_calls is empty but content is a JSON tool call, synthesize the tool call."""
    if ai_message.tool_calls or not ai_message.content:
        return ai_message
    try:
        data = json.loads(ai_message.content)
        name = data.get('name')
        args = data.get('arguments') or data.get('args') or {}
        if name and isinstance(args, dict):
            tool_call = {'name': name, 'args': args, 'id': 'coerced_0', 'type': 'tool_call'}
            return AIMessage(content='', tool_calls=[tool_call])
    except (json.JSONDecodeError, AttributeError):
        pass
    return ai_message
