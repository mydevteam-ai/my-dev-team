
class CommunicationLog:
    """Mixin to provide logging capabilities to agents and tools."""

    def communication(self, message: str | list[str]) -> list[str]:
        messages = [message] if isinstance(message, str) else message
        return [f"**[{self.__class__.__name__}]**: {msg}" for msg in messages if msg and msg.strip()]
