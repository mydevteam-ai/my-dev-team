from logging import Logger
from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph
from devteam.utils import sanitizer
from .event_emitter import EventEmitter
from .final_result import FinalResult

class Execution(EventEmitter):
    """Mixin to manage asynchronous execution."""

    app: CompiledStateGraph
    logger: Logger

    async def _inject_feedback(self, config: dict, feedback: str, feedback_source: str = 'reviewer') -> dict:
        """Inject feedback before resuming a thread."""
        state_update = {}
        if feedback_source == 'reviewer':
            state_update['review_feedback'] = f"CRITICAL HUMAN FEEDBACK: {feedback}"
            state_update['current_phase'] = 'development'
        elif feedback_source == 'qa':
            state_update['test_results'] = f"CRITICAL HUMAN FEEDBACK: {feedback}"
            state_update['current_phase'] = 'development'
        elif feedback_source == 'pm':
            state_update['specs'] = f"CRITICAL HUMAN FEEDBACK: {feedback}"
            state_update['current_phase'] = 'planning'
        else:
            state_update['communication_log'] = [f"**[Human]**: {feedback}"]
        target_state = await self.app.aget_state(config)
        safe_config = target_state.config.copy()
        if 'configurable' not in safe_config:
            safe_config['configurable'] = {}
        await self.app.aupdate_state(
            safe_config,
            state_update,
            as_node=feedback_source
        )
        return state_update

    async def execute(self, thread_id: str, *, requirements: str = None, feedback: str = None, feedback_source: str = 'reviewer', checkpoint_id: str = None) -> FinalResult:
        config = {'configurable': {'thread_id': thread_id}}
        if checkpoint_id:
            config['configurable']['checkpoint_id'] = checkpoint_id
            self.logger.debug("Rewinding time to checkpoint: %s", checkpoint_id)
        abort_requested = False
        if feedback:
            state_update = await self._inject_feedback(config, feedback, feedback_source)
            await self.emit_event('resume', thread_id, state_update=state_update)
            initial_state = None
        elif requirements:
            safe_requirements = sanitizer.sanitize_for_prompt(requirements, ['requirements'])
            content = (
                "Here are the new project requirements:\n\n"
                "<requirements>\n"
                f"{safe_requirements}\n"
                "</requirements>"
            )
            initial_state = {
                'requirements': requirements,
                'current_phase': 'planning',
                'messages': [HumanMessage(content=content)]
            }
            await self.emit_event('start', thread_id, initial_state=initial_state)
        else:
            initial_state = None
            await self.emit_event('resume', thread_id, state_update=initial_state)

        while True:
            async for event in self.app.astream(initial_state, config, stream_mode='updates'):
                state_update = event
                state_object = await self.app.aget_state(config)
                full_state = state_object.values
                await self.emit_event('step', thread_id, state_update=state_update, full_state=full_state)
                if full_state.get('abort_requested'):
                    abort_requested = True
                    self.logger.debug("Abort requested during execution. Ending workflow.")
                    break
            if abort_requested:
                break
            if initial_state:
                initial_state = None
            state_snapshot = await self.app.aget_state(config)
            if not state_snapshot.next:
                break
            next_node = state_snapshot.next[0]
            self.logger.debug("Workflow paused. Waiting on: %s", next_node)
            update = await self.emit_event('pause', thread_id, current_state=state_snapshot.values, next_node=next_node)
            if not update:
                break
            await self.app.aupdate_state(config, update)
            if update.get('abort_requested'):
                abort_requested = True
                self.logger.debug("Abort requested. Ending workflow.")
                break

        final_state = await self.app.aget_state(config)
        final_state = final_state.values
        if abort_requested:
            final_state['abort_requested'] = True
        else:
            final_state['current_phase'] = 'complete'
        await self.emit_event('finish', thread_id, final_state=final_state)
        final_state['thread_id'] = thread_id
        return FinalResult(**final_state)
