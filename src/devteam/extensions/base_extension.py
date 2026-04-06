from devteam.utils import CommunicationLog, WithLogging

class CrewExtension(CommunicationLog, WithLogging):
    """Base class for all Virtual Crew extensions."""

    critical: bool = False

    async def on_start(self, thread_id: str, initial_state: dict):
        """Triggered right before the crew starts running."""

    async def on_resume(self, thread_id: str, state_update: dict):
        """Triggered when resuming an existing workflow."""

    async def on_step(self, thread_id: str, state_update: dict, full_state: dict):
        """Triggered every time LangGraph updates the state."""

    async def on_pause(self, thread_id: str, current_state: dict, next_node: str) -> dict | None:
        """Triggered when the graph pauses (e.g. waiting for HITL)."""

    async def on_finish(self, thread_id: str, final_state: dict):
        """Triggered when the project successfully completes."""
