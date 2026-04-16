import asyncio
from functools import cached_property
from pathlib import Path
import re
import traceback
import yaml
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable
from pydantic import BaseModel
from devteam import settings
from devteam.skills import skills
from devteam.state import ProjectState
from devteam.tools.extractor import coerce_tool_calls
from devteam.utils import LLMFactory, RateLimiter, WithLogging, CommunicationLog, sanitizer, workspace
from devteam.utils import retrieve_workspace_context, retrieve_skills_context
from .intermediate_tools import IntermediateTools

_TAG_MAP = {'workspace_listing': 'workspace', 'workspace_context': 'workspace', 'skills_context': 'skills'}

def _prompt_tag(key: str) -> str:
    return _TAG_MAP.get(key, key)

class BaseAgent[T: BaseModel](CommunicationLog, IntermediateTools, WithLogging):
    """Base agent that uses LLM tool calling to submit structured results."""

    capabilities: dict[str, float]
    temperature: float = 0.2
    max_retries: int = 2
    rate_limiter: RateLimiter = None
    output_schema: type[T]

    def __init__(self, config: dict, prompt_template: str, node_name: str, llm_factory: LLMFactory = None, rate_limiter: RateLimiter = None):
        self.config = config
        self.prompt_template = prompt_template
        self.node_name = node_name
        self.llm_factory = llm_factory
        self.rate_limiter = rate_limiter
        self.role = config.get('role', 'Agent')
        self.name = config.get('name', None)
        self.capabilities = self._resolve_capabilities(config)
        self.temperature = config.get('temperature', self.temperature)

    @staticmethod
    def _resolve_capabilities(config: dict) -> dict[str, float]:
        """Read capabilities from config."""
        caps = config.get('capabilities')
        if isinstance(caps, list):
            return {cap: 1.0 for cap in caps}
        return dict(caps)

    @cached_property
    def inputs(self) -> list[str]:
        return self.config.get('inputs', [])

    @cached_property
    def outputs(self) -> list[str]:
        return self.config.get('outputs', [])

    def _build_inputs(self, state: ProjectState) -> dict:
        inputs = {}
        for key in self.inputs:
            match key:
                case 'skills':
                    inputs[key] = sanitizer.sanitize_for_prompt(self._skills_catalog, 'skills')
                case 'skills_context':
                    catalog = skills.load_skills_catalog()
                    query = getattr(state.task_context, 'current_task', '') or getattr(state, 'specs', '')
                    inputs[key] = sanitizer.sanitize_for_prompt(
                        retrieve_skills_context(catalog, query), 'skills'
                    )
                case 'workspace':
                    if workspace_files := workspace.read_all_files(state.workspace_path):
                        inputs[key] = workspace.workspace_str_from_files(workspace_files).strip()
                    else:
                        inputs[key] = "No files exist in the workspace."
                case 'workspace_context':
                    query = getattr(state.task_context, 'current_task', '') or getattr(state, 'specs', '')
                    if workspace.live_paths(state.workspace_path):
                        inputs[key] = retrieve_workspace_context(state.workspace_path, query)
                    else:
                        inputs[key] = "No files exist in the workspace."
                case 'workspace_listing':
                    inputs[key] = workspace.list_workspace_files(state.workspace_path)
                case _:
                    val = getattr(state, key, None)
                    if val is None:
                        val = getattr(state.task_context, key, '')
                    inputs[key] = sanitizer.sanitize_for_prompt(str(val), key) if val else ''
        return inputs

    def _update_state(self, parsed_data: T, current_state: ProjectState) -> dict:
        return parsed_data.model_dump(exclude_none=True)

    async def _pre_process(self, state: ProjectState) -> ProjectState:
        """Lifecycle Hook: performs actions BEFORE the LLM runs."""
        return state

    async def _post_process(self, state: ProjectState, final_state: dict) -> dict:
        """Lifecycle Hook: performs actions AFTER the LLM runs."""
        return final_state

    @staticmethod
    def _repair_tool_call_messages(messages: list) -> list:
        """Convert HumanMessages that follow tool_calls into ToolMessages to meet OpenAI API contract."""
        repaired = []
        i = 0
        while i < len(messages):
            msg = messages[i]
            repaired.append(msg)
            i += 1
            if not (isinstance(msg, AIMessage) and msg.tool_calls):
                continue
            answered_ids = set()
            while i < len(messages) and isinstance(messages[i], ToolMessage):
                repaired.append(messages[i])
                answered_ids.add(messages[i].tool_call_id)
                i += 1
            unanswered = [tc for tc in msg.tool_calls if tc['id'] not in answered_ids]
            if unanswered and i < len(messages) and isinstance(messages[i], HumanMessage):
                human_content = messages[i].content
                for tc in unanswered:
                    repaired.append(ToolMessage(content=human_content, tool_call_id=tc['id']))
                i += 1
        return repaired

    async def process(self, state: ProjectState) -> dict:
        """Invoke LLM and use tools to provide structured results."""
        if isinstance(state, dict):
            state = ProjectState(**state)
        self.logger.info("Executing...")
        state = await self._pre_process(state)
        inputs = self._build_inputs(state)
        original_messages = self._repair_tool_call_messages(list(state.messages))
        if 'messages' not in inputs:
            inputs['messages'] = original_messages
        last_error = ''
        no_tool_call_retry = False
        for attempt in range(self.max_retries + 1):
            if attempt > 0:
                self.logger.warning("LLM call failed. Retrying (attempt %d/%d)...", attempt + 1, self.max_retries + 1)
                inputs['messages'] = list(original_messages)
                if no_tool_call_retry:
                    tool_names = ', '.join(t.__name__ for t in self.tools)
                    inputs['messages'] = inputs['messages'] + [HumanMessage(content=(
                        f"You must respond by calling one of the available tools: {tool_names}. "
                        "Do not return plain text - use a tool call to submit your response."
                    ))]
                    self.logger.debug("Injected tool-call reminder into retry messages.")
            no_tool_call_retry = False
            conversation_history = []
            try:
                while True:
                    if conversation_history:
                        inputs['messages'] = original_messages + conversation_history
                    self.logger.debug("Invoking LLM with inputs:\n%s", inputs)
                    ai_message = await self._invoke_llm(**inputs)
                    ai_message = coerce_tool_calls(ai_message)
                    conversation_history.append(ai_message)
                    if not ai_message.tool_calls:
                        no_tool_call_retry = True
                        raise ValueError("The model did not call any tool.")
                    intermediate_results = await asyncio.gather(
                        *[self._handle_intermediate_tools(tc['name'], tc['args'], state) for tc in ai_message.tool_calls]
                    )
                    if any(r is not None for r in intermediate_results):
                        for tc, result in zip(ai_message.tool_calls, intermediate_results):
                            tool_msg = ToolMessage(content=result or '', tool_call_id=tc['id'])
                            conversation_history.append(tool_msg)
                        continue
                    parsed_data = self._parse_outputs(ai_message)
                    break
                break
            except ImportError as e:
                self.logger.error("%s", e)
                return {'error': True, 'error_message': str(e)}
            except Exception as exc: # pylint: disable=broad-exception-caught
                last_error = traceback.format_exc()
                self.logger.error("Attempt %d/%d failed:\n%s", attempt + 1, self.max_retries + 1, last_error)
                if 'attempted to call tool' in str(exc) or 'tool call validation' in str(exc):
                    no_tool_call_retry = True
        else:
            return {
                'error': True,
                'error_message': last_error,
            }
        final_state = self._update_state(parsed_data, state)
        final_state = await self._post_process(state, final_state)
        if 'messages' in self.outputs:
            final_state['messages'] = conversation_history
        final_state['communication_log'] = self.communication(ai_message.content)
        return final_state

    @cached_property
    def _skills_catalog(self) -> str:
        if catalog := skills.load_skills_catalog():
            return '\n'.join(f"- `{item['name']}`: {item['description']}" for item in catalog)
        return "No skills available."

    @cached_property
    def _llm(self) -> Runnable:
        llm = self.llm_factory.create(
            capabilities=self.capabilities,
            temperature=self.temperature,
            node_name=self.node_name,
            json_mode=False
        )
        return llm.bind_tools(self.tools)

    def _data_input_keys(self) -> list[str]:
        """Input keys that become template variables in the human message (all inputs except messages)."""
        return [k for k in self.inputs if k != 'messages']

    def _build_prompt(self) -> ChatPromptTemplate:
        data_keys = self._data_input_keys()
        human_parts = []
        for key in data_keys:
            tag = _prompt_tag(key)
            human_parts.append(f"<{tag}>\n{{{key}}}\n</{tag}>")
        messages = [('system', self.prompt_template)]
        if human_parts:
            messages.append(('human', '\n\n'.join(human_parts)))
        messages.append(MessagesPlaceholder(variable_name='messages'))
        return ChatPromptTemplate.from_messages(messages)

    @cached_property
    def _chain(self) -> Runnable:
        return self._build_prompt() | self._llm

    async def _invoke_llm(self, **kwargs) -> AIMessage:
        if self.rate_limiter:
            await self.rate_limiter.wait_if_needed()
        try:
            response = await asyncio.wait_for(
                self._chain.ainvoke(kwargs), timeout=settings.llm_timeout
            )
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"LLM call timed out after {settings.llm_timeout} seconds"
            ) from None
        self.logger.debug("Raw Response Content:\n%s", response.content)
        self.logger.debug("Tool Calls:\n%s", response.tool_calls)
        return response

    def _parse_outputs(self, response) -> T:
        if not response.tool_calls:
            raise ValueError(
                "The model did not call any tool. "
                "You MUST call one of the provided tools to submit your work."
            )
        tool_call = response.tool_calls[0]
        return self._map_tool_to_output(tool_call['name'], tool_call['args'])

    def _map_tool_to_output(self, tool_name: str, tool_args: dict) -> T:
        """Map a tool call to the agent's output schema."""
        return self.output_schema(**tool_args)

    @staticmethod
    def _resolve_includes(prompt: str, base_dir: Path) -> str:
        base = base_dir.resolve()
        def replacer(match):
            filepath = match.group(1)
            resolved = (base / filepath).resolve()
            if not resolved.is_relative_to(base):
                raise ValueError(f"Include path '{filepath}' escapes the base directory")
            try:
                return resolved.read_text(encoding='utf-8').strip()
            except FileNotFoundError:
                raise FileNotFoundError(f"Include '{filepath}' not found in {base}") from None
        return re.sub(r"\{\s*include\s+'([^']+)'\s*\}", replacer, prompt)

    @classmethod
    def from_config(cls, node_name: str, config_path: str, *, llm_factory: LLMFactory = None, rate_limiter: RateLimiter = None, capabilities: dict[str, float] | list[str] = None, temperature: float = None):
        prompt_file = settings.config_dir / 'agents' / config_path
        try:
            content = prompt_file.read_text(encoding='utf-8')
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Could not find agent prompt '{config_path}' in {prompt_file.parent}") from e
        parts = content.split('---', 2)
        if len(parts) < 3:
            raise ValueError(f"Invalid format in {config_path}. Missing YAML frontmatter")
        config = yaml.safe_load(parts[1])
        prompt = cls._resolve_includes(parts[2].strip(), prompt_file.parent)
        if capabilities is not None:
            config['capabilities'] = capabilities
        if temperature is not None:
            config['temperature'] = temperature
        return cls(config, prompt, node_name, llm_factory=llm_factory, rate_limiter=rate_limiter)
