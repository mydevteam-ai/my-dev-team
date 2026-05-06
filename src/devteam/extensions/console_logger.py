from typing import override
from rich import print # pylint: disable=redefined-builtin
from rich.panel import Panel
from rich.text import Text
from .base_extension import CrewExtension

_TRUNCATE_FIELDS = {'specs', 'final_report', 'current_task', 'requirements', 'raw_test_results', 'test_results', 'review_feedback'}
_MAX_VALUE_LENGTH = 200
_TASK_CONTEXT_SUMMARY_FIELDS = ('current_agent', 'current_task_name', 'current_task_complexity', 'revision_count', 'winner_developer')

def _describe_message(msg) -> str:
    msg_type = getattr(msg, 'type', msg.__class__.__name__)
    if getattr(msg, 'tool_calls', None):
        return f"{msg_type}+tool_call"
    return msg_type

def _format_value(key: str, value) -> str:
    """Format a state value for console display, truncating large content."""
    if key == 'messages' and isinstance(value, list):
        if not value:
            return '[]'
        return f"[{len(value)} message(s), last: {_describe_message(value[-1])}]"
    if key == 'pending_tasks' and isinstance(value, list):
        names = [t.get('task_name', '?') for t in value]
        return f"[{len(names)} task(s): {', '.join(names)}]"
    if key == 'communication_log' and isinstance(value, list):
        return f"[{len(value)} entry(s)]"
    if key == 'developer_drafts' and isinstance(value, dict):
        files = set()
        for drafts in value.values():
            if isinstance(drafts, dict):
                files.update(drafts.keys())
        if not files:
            return '{}'
        return f"[{len(value)} developer(s), {len(files)} file(s): {', '.join(sorted(files))}]"
    if key == 'task_context':
        parts = []
        for field_name in _TASK_CONTEXT_SUMMARY_FIELDS:
            sub = getattr(value, field_name, None)
            if sub in (None, '', 0):
                continue
            parts.append(f"{field_name}={sub!r}")
        drafts = getattr(value, 'developer_drafts', None)
        if drafts:
            parts.append(f"developer_drafts={_format_value('developer_drafts', drafts)}")
        return '(' + ', '.join(parts) + ')' if parts else '(empty)'
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
        new_logs: list[str] = []
        for node_name, node_output in state_update.items():
            if not isinstance(node_output, dict):
                continue
            new_logs.extend(node_output.get('communication_log') or [])
            lines = Text()
            for key, value in node_output.items():
                if value is None or value == '' or value == [] or value == {}:
                    continue
                formatted = _format_value(key, value)
                lines.append(key, style='bold cyan')
                lines.append(f": {formatted}\n")
            if lines:
                print(Panel(lines, title=f"[bold yellow]📍 {node_name}[/bold yellow]", border_style="dim"))

        for entry in new_logs:
            first_line = entry.splitlines()[0] if entry else ''
            _, sep, content = first_line.partition(': ')
            if (sep and content.strip()) or (not sep and first_line.strip()):
                print(f"  [bold]➜[/bold] {first_line}")

    @override
    async def on_finish(self, thread_id: str, final_state: dict):
        print(f"\n[bold green]✅ FINISHED THREAD: {thread_id}[/bold green]")
        if tasks := final_state.get('pending_tasks'):
            print(f"[dim]Generated {len(tasks)} tasks for the backlog.[/dim]")
        elif code := final_state.get('code'):
            print(f"[dim]Code updated. Revisions took: {final_state.get('revision_count', 0)}[/dim]")
        elif report := final_state.get('final_report'):
            print("[dim]Release report generated successfully.[/dim]")
