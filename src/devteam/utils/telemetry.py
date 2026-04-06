from collections import defaultdict
from functools import cached_property
from typing import TypedDict
import yaml
from rich.panel import Panel
from rich.table import Table
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from litellm import cost_per_token
from devteam import settings
from .with_logging import WithLogging
from .cost_optimization import CostOptimization

class CallRecord(TypedDict):
    agent: str
    input_tokens: int
    output_tokens: int
    iteration: int

class TelemetryTracker(BaseCallbackHandler, CostOptimization, WithLogging):
    """Tracks token usage and estimates costs across all agent LLM calls"""
    def __init__(self):
        self.total_requests = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_cost = 0.0
        self.call_history: list[CallRecord] = []
        self.agent_calls = defaultdict(int)

    def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        """Fires automatically every time an LLM finishes generating text"""
        self.total_requests += 1
        metadata = self._extract_metadata(response)
        self.input_tokens += metadata['input_tokens']
        self.output_tokens += metadata['output_tokens']
        self.total_cost += self._calculate_cost(metadata['model_provider'], metadata['model_name'], metadata['input_tokens'], metadata['output_tokens'])
        self.logger.debug("Accumulated: %i %i %.6f", self.input_tokens, self.output_tokens, self.total_cost)
        tags = kwargs.get('tags', [])
        agent_name = next(
            (tag.split(':', maxsplit=1)[1] for tag in tags if isinstance(tag, str) and tag.startswith('node:')),
            'unknown'
        )
        self.agent_calls[agent_name] += 1
        self.call_history.append(CallRecord(
            agent=agent_name,
            input_tokens=metadata['input_tokens'],
            output_tokens=metadata['output_tokens'],
            iteration=self.agent_calls[agent_name]
        ))

    def _extract_metadata(self, response) -> dict:
        input_tokens = 0
        output_tokens = 0
        model_provider = 'unknown'
        model_name = 'unknown'
        for idx, generation in enumerate(x for row in response.generations for x in row):
            model_provider = generation.message.response_metadata.get('model_provider', 'unknown')
            model_name = generation.message.response_metadata.get('model_name', 'unknown')
            usage = generation.message.usage_metadata or {}
            if idx == 0:  # Prompt tokens are shared across all generations — only count once
                input_tokens = usage.get('input_tokens', 0)
            output_tokens += usage.get('output_tokens', 0)
        self.logger.debug("Generation: %s/%s %i %i", model_provider, model_name, input_tokens, output_tokens)
        return {
            'model_provider': model_provider,
            'model_name': model_name,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens
        }

    @cached_property
    def llm_aliases(self) -> dict:
        try:
            config_path = settings.tools_config_dir / 'llms.yaml'
            config = yaml.safe_load(config_path.read_text(encoding='utf-8'))
            return config.get('aliases', {})
        except Exception: # pylint: disable=broad-exception-caught
            return {}

    def _calculate_cost(self, model_provider: str, model_name: str, input_tokens: int, output_tokens: int):
        """Calculates the cost based on the specific model used"""
        if model_provider == 'ollama':
            return 0
        try:
            model_name = self.llm_aliases.get(model_name, model_name)
            p_cost, c_cost = cost_per_token(
                model=f'{model_provider}/{model_name}',
                prompt_tokens=input_tokens,
                completion_tokens=output_tokens
            )
            return p_cost + c_cost
        except Exception as e: # pylint: disable=broad-exception-caught
            self.logger.error("Cost calculation failed for %s/%s: %s", model_provider, model_name, e)
            return 0

    def get_receipt_panel(self, panel_width: int = 75) -> Panel:
        table = Table(show_header=False, box=None, expand=True)
        table.add_column("Metric", style='cyan', no_wrap=True)
        table.add_column("Value", justify='right', style='yellow')
        table.add_row("Total API Requests:", str(self.total_requests))
        table.add_row("Prompt Tokens:", f"{self.input_tokens:,}")
        table.add_row("Completion Tokens:", f"{self.output_tokens:,}")
        table.add_row("Total Tokens:", f"{self.input_tokens + self.output_tokens:,}")
        table.add_row("", "")
        table.add_row("[bold white]Estimated Cost:[/bold white]", f"[bold green]${self.total_cost:.4f}[/bold green]")
        return Panel(
            table,
            title="[bold white]📊 TELEMETRY & COST REPORT[/bold white]",
            border_style='blue',
            width=panel_width,
            padding=(1, 3)
        )
