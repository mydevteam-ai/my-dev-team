from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

_ALLOWED_MODULES = [
    ('devteam.state.task_context', 'TaskContext'),
]

def create_serde() -> JsonPlusSerializer:
    """Create a checkpoint serializer with project-specific types whitelisted."""
    return JsonPlusSerializer(allowed_msgpack_modules=_ALLOWED_MODULES)
