from typing import override
from rich import print # pylint: disable=redefined-builtin
from rich.panel import Panel
from rich.text import Text
from .base_extension import CrewExtension

_TRUNCATE_FIELDS = {'specs', 'final_report', 'current_task', 'requirements'}
_MAX_VALUE_LENGTH = 200

def _format_value(key: str, value) -> str:
    """Format a state value for console display, truncating large content."""
    if key == 'pending_tasks' and isinstance(value, list):
        names = [t.get('task_name', '?') for t in value]
        return f"[{len(names)} task(s): {', '.join(names)}]"
    if key == 'communication_log' and isinstance(value, list):
        return f"[{len(value)} entry(s)]"
    text = str(value)
    if key in _TRUNCATE_FIELDS and len(text) > _MAX_VALUE_LENGTH:
        return text[:_MAX_VALUE_LENGTH] + f'... ({len(text)} chars)'
    return text

class ConsoleLogger(CrewExtension):
    @override
    async def on_start(self, thread_id: str, initial_state: dict):
        print(f"\n[bold green]🚀 STARTING THREAD: {thread_id}[/bold green]")
        if 'requirements' in initial_state and 'pending_tasks' not in initial_state:
            print("[dim]Phase: 📋 Planning (Backlog Creation)[/dim]")
        elif 'current_task' in initial_state:
            print(f"[dim]Phase: 💻 Execution (Task: {initial_state.get('current_task')})[/dim]")
        elif 'code' in initial_state and 'final_report' in initial_state:
            print("[dim]Phase: 📦 Release & Integration[/dim]")

    @override
    async def on_resume(self, thread_id: str, state_update: dict):
        print(f"[bold cyan] 🔄 RESUMING THREAD: {thread_id}[/bold cyan]")
        if state_update and len(state_update) > 0:
            print("[dim]Injecting human feedback[/dim]")

    @override
    async def on_step(self, thread_id: str, state_update: dict, full_state: dict):
        for node_name, node_output in state_update.items():
            if not isinstance(node_output, dict):
                continue
            lines = Text()
            for key, value in node_output.items():
                if value is None or value == '' or value == [] or value == {}:
                    continue
                formatted = _format_value(key, value)
                lines.append(key, style='bold cyan')
                lines.append(f": {formatted}\n")
            if lines:
                print(Panel(lines, title=f"[bold yellow]📍 {node_name}[/bold yellow]", border_style="dim"))

        logs = full_state.get('communication_log', [])
        if logs:
            latest_log = logs[-1]
            print(f"  [bold]➜[/bold] {latest_log.splitlines()[0]}")

    @override
    async def on_finish(self, thread_id: str, final_state: dict):
        print(f"\n[bold green]✅ FINISHED THREAD: {thread_id}[/bold green]")
        if tasks := final_state.get('pending_tasks'):
            print(f"[dim]Generated {len(tasks)} tasks for the backlog.[/dim]")
        elif code := final_state.get('code'):
            print(f"[dim]Code updated. Revisions took: {final_state.get('revision_count', 0)}[/dim]")
        elif report := final_state.get('final_report'):
            print("[dim]Release report generated successfully.[/dim]")
