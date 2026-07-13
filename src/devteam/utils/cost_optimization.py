from typing import Any
from rich.panel import Panel
from rich.table import Table
from rich import box

# Fractions of the routed model's context window that trigger a warning (mirrors my-dev-team-vs-code)
CONTEXT_FILL_THRESHOLDS = (0.75, 0.85, 0.95)

_KIND_STYLES = {
    'thrashing': ('bold yellow', '⚠️ Thrashing'),
    'context_bloat': ('bold yellow', '📈 Context Bloat'),
    'high_waste': ('bold red', '🗑️ High Waste'),
    'context_pressure': ('bold red', '🪟 Context Pressure'),
}

class CostOptimization:
    call_history: list[dict[str, Any]]
    agent_calls: dict[str, int]

    def collect_diagnostics(self) -> list[dict]:
        """Analyze the call history and return plain-data warnings (rendered by the CLI panel and the GUI)."""
        warnings_data = []
        # 1. Detect Thrashing (too many loops for one agent)
        for agent, count in self.agent_calls.items():
            if count > 5:
                warnings_data.append({
                    'kind': 'thrashing',
                    'agent': agent,
                    'detail': f"Called {count} times. Possible failure loop."
                })
        # 2. Detect Context Bloat (Input tokens growing exponentially)
        for agent in {c['agent'] for c in self.call_history}:
            agent_calls = [c for c in self.call_history if c['agent'] == agent]
            if len(agent_calls) > 2:
                first_input = agent_calls[0]['input_tokens']
                last_input = agent_calls[-1]['input_tokens']
                if first_input > 0 and (last_input / first_input) > 2.5:
                    growth = last_input / first_input
                    warnings_data.append({
                        'kind': 'context_bloat',
                        'agent': agent,
                        'detail': f"Input grew by {growth:.1f}x (Started: {first_input}, Ended: {last_input})."
                    })
        # 3. Detect High Waste Ratio (Massive input, tiny output)
        for call in self.call_history:
            if call['input_tokens'] > 5000 and call['output_tokens'] < 50:
                warnings_data.append({
                    'kind': 'high_waste',
                    'agent': call['agent'],
                    'detail': f"Received {call['input_tokens']} tokens but generated only {call['output_tokens']}."
                })
                break
        # 4. Detect Context Pressure (input tokens near the routed model's context window)
        peaks: dict[str, dict] = {}
        for call in self.call_history:
            fill = call.get('context_fill')
            if fill and fill >= CONTEXT_FILL_THRESHOLDS[0] and fill > peaks.get(call['agent'], {}).get('fill', 0.0):
                peaks[call['agent']] = {'fill': fill, 'model': call.get('model', 'unknown')}
        for agent, peak in peaks.items():
            warnings_data.append({
                'kind': 'context_pressure',
                'agent': agent,
                'detail': f"Peak context fill {peak['fill']:.0%} of the {peak['model']} window."
            })
        return warnings_data

    def get_optimization_panel(self, panel_width: int = 75) -> Panel:
        if warnings_data := self.collect_diagnostics():
            table = Table(show_edge=False, show_lines=True, box=box.SIMPLE)
            table.add_column("Issue Type", justify='left')
            table.add_column("Agent", justify='center')
            table.add_column("Diagnostic Detail", justify='left')
            for warning in warnings_data:
                style, label = _KIND_STYLES[warning['kind']]
                table.add_row(f"[{style}]{label}[/{style}]", f"[cyan]{warning['agent']}[/cyan]", warning['detail'])
            return Panel(
                table,
                title="[bold red]🔍 TOKEN OPTIMIZATION DIAGNOSTICS[/bold red]",
                border_style='red',
                width=panel_width,
                padding=(0, 1)
            )
        return Panel(
            "[bold green]✅ No major token leakage detected. Highly efficient run![/bold green]",
            title="[bold green]🔍 TOKEN OPTIMIZATION DIAGNOSTICS[/bold green]",
            border_style='green',
            width=panel_width,
            padding=(1, 3)
        )
