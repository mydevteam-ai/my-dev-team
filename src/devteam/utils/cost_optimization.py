from typing import Any
from rich.panel import Panel
from rich.table import Table
from rich import box

class CostOptimization:
    call_history: list[dict[str, Any]]
    agent_calls: dict[str, int]

    def get_optimization_panel(self, panel_width: int = 75) -> Panel:
        warnings_data = []
        # 1. Detect Thrashing (too many loops for one agent)
        for agent, count in self.agent_calls.items():
            if count > 5:
                warnings_data.append((
                    "[bold yellow]⚠️ Thrashing[/bold yellow]",
                    f"[cyan]{agent}[/cyan]",
                    f"Called [bold red]{count}[/bold red] times. Possible failure loop."
                ))
        # 2. Detect Context Bloat (Input tokens growing exponentially)
        for agent in {c['agent'] for c in self.call_history}:
            agent_calls = [c for c in self.call_history if c['agent'] == agent]
            if len(agent_calls) > 2:
                first_input = agent_calls[0]['input_tokens']
                last_input = agent_calls[-1]['input_tokens']
                if first_input > 0 and (last_input / first_input) > 2.5:
                    growth = last_input / first_input
                    warnings_data.append((
                        "[bold yellow]📈 Context Bloat[/bold yellow]",
                        f"[cyan]{agent}[/cyan]",
                        f"Input grew by [bold red]{growth:.1f}x[/bold red] (Started: {first_input}, Ended: {last_input})."
                    ))
        # 3. Detect High Waste Ratio (Massive input, tiny output)
        waste_flagged = False
        for call in self.call_history:
            if call['input_tokens'] > 5000 and call['output_tokens'] < 50 and not waste_flagged:
                warnings_data.append((
                    "[bold red]🗑️ High Waste[/bold red]",
                    f"[cyan]{call['agent']}[/cyan]",
                    f"Received {call['input_tokens']} tokens but generated only {call['output_tokens']}."
                ))
                waste_flagged = True
        # 4. Render the output dynamically based on findings
        if warnings_data:
            table = Table(show_edge=False, show_lines=True, box=box.SIMPLE)
            table.add_column("Issue Type", justify='left')
            table.add_column("Agent", justify='center')
            table.add_column("Diagnostic Detail", justify='left')
            for w_type, w_agent, w_detail in warnings_data:
                table.add_row(w_type, w_agent, w_detail)
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
