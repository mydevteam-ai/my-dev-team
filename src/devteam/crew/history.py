from langgraph.graph import END
from langgraph.graph.state import CompiledStateGraph

class History:
    """Mixin for show history functionality."""

    app: CompiledStateGraph

    async def get_history(self, thread_id: str) -> list[dict]:
        config = {'configurable': {'thread_id': thread_id}}
        all_checkpoints = []
        seen_c_ids = set()
        async for state_snapshot in self.app.aget_state_history(config):
            c_id = state_snapshot.config['configurable']['checkpoint_id']
            if c_id not in seen_c_ids:
                all_checkpoints.append({
                    'time': state_snapshot.created_at,
                    'c_id': c_id,
                    'node': state_snapshot.next[0] if state_snapshot.next else END
                })
                seen_c_ids.add(c_id)
        all_checkpoints.sort(key=lambda x: x['time'], reverse=True)
        return all_checkpoints
