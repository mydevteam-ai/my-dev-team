import asyncio
from functools import cached_property
from pathlib import Path
import re
import traceback
import yaml
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable
from pydantic import BaseModel, ValidationError
from devteam import settings
from devteam.skills import skills
from devteam.state import ProjectState
from devteam.tools.extractor import coerce_tool_calls
from devteam.utils import LLMFactory, RateLimiter, WithLogging, CommunicationLog, sanitizer, workspace
from devteam.utils import retrieve_workspace_context, retrieve_skills_context, retry_delay, steering_for
from devteam.utils.rate_limiter import MAX_RATE_LIMIT_RETRIES
from devteam.utils.telemetry import REPAIRED_TAG
from .intermediate_tools import IntermediateTools

class NoToolCallError(Exception):
    """Raised when the LLM responds without calling any tool. Triggers a retry that injects a tool-call reminder into the next prompt."""


def input_handler(tag):
    """Defines a prompt tag used to wrap the rendered value."""
    def deco(fn):
        fn.tag = tag
        return fn
    return deco


def _resolve_capabilities(value) -> dict[str, float]:
    if isinstance(value, list):
        return {cap: 1.0 for cap in value}
    return dict(value)


class ConfigField:
    """Non-data descriptor that lazily reads a value from `obj.config`."""

    def __init__(self, default=None, transform=None):
        self.default = default
        self.transform = transform

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        value = obj.config.get(self.name, self.default)
        if self.transform is not None:
            value = self.transform(value)
        obj.__dict__[self.name] = value
        return value


class BaseAgent[T: BaseModel](CommunicationLog, IntermediateTools, WithLogging):
    """Base agent that uses LLM tool calling to submit structured results."""

    max_retries: int = 2
    rate_limiter: RateLimiter = None
    output_schema: type[T]

    role = ConfigField(default='Agent')
    name = ConfigField(default=None)
    capabilities = ConfigField(transform=_resolve_capabilities)
    temperature = ConfigField(default=0.2)
    top_k = ConfigField(default=None)
    top_p = ConfigField(default=None)
    complexity_routing = ConfigField(default=False, transform=bool)
    complexity_overrides = ConfigField(transform=lambda v: v or {})

    def __init__(self, config: dict, prompt_template: str, node_name: str, llm_factory: LLMFactory = None, rate_limiter: RateLimiter = None):
        self.config = config
        self.prompt_template = prompt_template
        self.node_name = node_name
        self.llm_factory = llm_factory
        self.rate_limiter = rate_limiter
        self._chain_cache: dict[str, Runnable] = {}
        self._chain_providers: dict[str, str] = {}

    @cached_property
    def inputs(self) -> list[str]:
        return self.config.get('inputs', [])

    @cached_property
    def outputs(self) -> list[str]:
        return self.config.get('outputs', [])

    def _build_inputs(self, state: ProjectState) -> dict:
        inputs = {}
        for key in self.inputs:
            if handler := getattr(self, f'_input_{key}', None):
                inputs[key] = handler(state)
            else:
                inputs[key] = self._input_state_attr(state, key)
        return inputs

    def _input_skills(self, state: ProjectState) -> str:
        return sanitizer.sanitize_for_prompt(self._skills_catalog, 'skills')

    @input_handler(tag='skills')
    def _input_skills_context(self, state: ProjectState) -> str:
        catalog = skills.load_skills_catalog()
        return sanitizer.sanitize_for_prompt(retrieve_skills_context(catalog, self._task_query(state)), 'skills')

    def _input_workspace(self, state: ProjectState) -> str:
        if files := workspace.read_all_files(state.workspace_path):
            return workspace.workspace_str_from_files(files).strip()
        return "No files exist in the workspace."

    @input_handler(tag='workspace')
    def _input_workspace_context(self, state: ProjectState) -> str:
        if not workspace.live_paths(state.workspace_path):
            return "No files exist in the workspace."
        return retrieve_workspace_context(state.workspace_path, self._task_query(state))

    @input_handler(tag='workspace')
    def _input_workspace_listing(self, state: ProjectState) -> str:
        return workspace.list_workspace_files(state.workspace_path)

    def _input_state_attr(self, state: ProjectState, key: str) -> str:
        val = getattr(state, key, None) or getattr(state.task_context, key, '')
        return sanitizer.sanitize_for_prompt(str(val), key) if val else ''

    @staticmethod
    def _task_query(state: ProjectState) -> str:
        return getattr(state.task_context, 'current_task', '') or getattr(state, 'specs', '')

    def _prompt_tag(self, key: str) -> str:
        return getattr(getattr(self, f'_input_{key}', None), 'tag', key)

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
        complexity = self._resolve_complexity(state)
        if complexity:
            self.logger.info("Routing on complexity=%s", complexity)
        inputs = self._build_inputs(state)
        base_messages = self._repair_tool_call_messages(list(state.messages))
        last_error = ''
        repair_message = None
        for attempt in range(self.max_retries + 1):
            if attempt > 0:
                self.logger.warning("LLM call failed. Retrying (attempt %d/%d)...", attempt + 1, self.max_retries + 1)
            messages = self._with_repair_message(base_messages, repair_message) if repair_message else base_messages
            repaired = repair_message is not None
            repair_message = None
            try:
                parsed_data, conversation_history = await self._run_attempt(inputs, messages, complexity, state, repaired=repaired)
                break
            except ImportError as e:
                self.logger.exception("Import error")
                return {'error': True, 'error_message': str(e)}
            except NoToolCallError:
                last_error = traceback.format_exc()
                self.logger.exception("Attempt %d/%d failed - no tool call", attempt + 1, self.max_retries + 1)
                repair_message = self._tool_reminder()
            except ValidationError as exc:
                last_error = traceback.format_exc()
                self.logger.exception("Attempt %d/%d failed - schema validation", attempt + 1, self.max_retries + 1)
                repair_message = self._repair_instruction(exc)
            except Exception as exc: # pylint: disable=broad-exception-caught
                last_error = traceback.format_exc()
                self.logger.exception("Attempt %d/%d failed", attempt + 1, self.max_retries + 1)
                if self._is_tool_validation_error(exc):
                    repair_message = self._tool_reminder()
        else:
            return {'error': True, 'error_message': last_error}
        final_state = self._update_state(parsed_data, state)
        final_state = await self._post_process(state, final_state)
        if 'messages' in self.outputs:
            final_state['messages'] = conversation_history
        tool_log = self._collect_tool_call_log(conversation_history)
        text_log = self.communication(conversation_history[-1].content)
        final_state['communication_log'] = tool_log + text_log
        return final_state

    async def _run_attempt(self, inputs: dict, messages: list, complexity: str, state: ProjectState, repaired: bool = False) -> tuple[T, list]:
        conversation_history = []
        while True:
            attempt_inputs = {**inputs, 'messages': messages + conversation_history}
            self.logger.debug("Invoking LLM with inputs:\n%s", attempt_inputs)
            ai_message = coerce_tool_calls(await self._invoke_llm(complexity=complexity, repaired=repaired, **attempt_inputs))
            # Only the call answering the corrective message is a repair;
            # follow-up intermediate-tool calls are normal continuation.
            repaired = False
            conversation_history.append(ai_message)
            if not ai_message.tool_calls:
                raise NoToolCallError("The model did not call any tool.")
            for tc in ai_message.tool_calls:
                self.logger.info("Tool call: %s", self._format_tool_call(tc))
            intermediate_results = await asyncio.gather(
                *[self._handle_intermediate_tools(tc['name'], tc['args'], state) for tc in ai_message.tool_calls]
            )
            if any(r is not None for r in intermediate_results):
                for tc, result in zip(ai_message.tool_calls, intermediate_results):
                    conversation_history.append(ToolMessage(content=result or '', tool_call_id=tc['id']))
                continue
            return self._parse_outputs(ai_message, state), conversation_history

    _TOOL_ARG_MAX_LEN: int = 60

    @classmethod
    def _format_tool_arg(cls, value) -> str:
        text = repr(value) if isinstance(value, str) else str(value)
        if len(text) > cls._TOOL_ARG_MAX_LEN:
            text = text[:cls._TOOL_ARG_MAX_LEN] + '...'
        return text

    @classmethod
    def _format_tool_call(cls, tool_call: dict) -> str:
        name = tool_call.get('name', 'tool')
        args = tool_call.get('args') or {}
        parts = [f"{key}={cls._format_tool_arg(value)}" for key, value in args.items()]
        return f"{name}({', '.join(parts)})"

    def _collect_tool_call_log(self, conversation_history: list) -> list[str]:
        """Build communication-log entries describing every intermediate tool call (excludes the final output tool)."""
        entries: list[str] = []
        for msg in conversation_history[:-1]:
            for tc in getattr(msg, 'tool_calls', None) or ():
                entries.append(f"**[{self.__class__.__name__}]** uses {self._format_tool_call(tc)}")
        return entries

    def _with_repair_message(self, messages: list, repair_message: str) -> list:
        self.logger.debug("Injected repair message into retry messages: %s", repair_message)
        return messages + [HumanMessage(content=repair_message)]

    def _tool_reminder(self) -> str:
        tool_names = ', '.join(t.__name__ for t in self.tools)
        return (
            f"You must respond by calling one of the available tools: {tool_names}. "
            "Do not return plain text - use a tool call to submit your response."
        )

    @staticmethod
    def _repair_instruction(error: ValidationError) -> str:
        """Render a schema-validation failure as a short, model-facing instruction."""
        issues = '; '.join(
            f"{'.'.join(str(loc) for loc in issue['loc']) or '(root)'}: {issue['msg']}"
            for issue in error.errors()
        )
        return (
            f"Your previous response failed validation: {issues}. "
            "Call the tool again with the corrected arguments - emit only the corrected tool call, with no commentary."
        )

    @staticmethod
    def _is_tool_validation_error(exc: Exception) -> bool:
        msg = str(exc)
        return 'attempted to call tool' in msg or 'tool call validation' in msg

    @cached_property
    def _skills_catalog(self) -> str:
        if catalog := skills.load_skills_catalog():
            return '\n'.join(f"- `{item['name']}`: {item['description']}" for item in catalog)
        return "No skills available."

    def _resolve_complexity(self, state: ProjectState) -> str:
        if not self.complexity_routing or settings.no_complexity_routing:
            return None
        task_ctx = getattr(state, 'task_context', None)
        if task_ctx and (c := getattr(task_ctx, 'current_task_complexity', '')):
            return c
        return getattr(state, 'project_complexity', None)

    def _resolve_params(self, complexity: str) -> tuple[float, dict]:
        extras = {k: v for k, v in {'top_k': self.top_k, 'top_p': self.top_p}.items() if v is not None}
        temperature = self.temperature
        if complexity and (override := self.complexity_overrides.get(complexity)):
            temperature = override.get('temperature', temperature)
            extras.update({k: override[k] for k in ('thinking', 'top_k', 'top_p') if k in override})
        return temperature, extras

    def _get_llm(self, complexity: str, model: dict = None) -> Runnable:
        temperature, extras = self._resolve_params(complexity)
        llm = self.llm_factory.create(
            capabilities=self.capabilities,
            temperature=temperature,
            node_name=self.node_name,
            json_mode=False,
            complexity=complexity,
            model=model,
            **extras,
        )
        return llm.bind_tools(self.tools)

    def _get_chain(self, complexity: str) -> Runnable:
        cache_key = complexity or '_default'
        if cache_key not in self._chain_cache:
            model = self.llm_factory.select_model(self.capabilities, complexity=complexity)
            # The real backend of the routed model: a compound provider's
            # entries carry their own provider field, so a `free` run charges
            # its Groq calls to the Groq budget, not the Ollama one.
            self._chain_providers[cache_key] = model.get('provider', self.llm_factory.provider)
            steering = steering_for(model.get('capabilities', {}))
            if steering:
                self.logger.debug("Steering for model %s:\n%s", model.get('id'), steering)
            self._chain_cache[cache_key] = self._build_prompt(steering) | self._get_llm(complexity, model)
        return self._chain_cache[cache_key]

    def _data_input_keys(self) -> list[str]:
        """Input keys that become template variables in the human message (all inputs except messages)."""
        return [k for k in self.inputs if k != 'messages']

    def _build_prompt(self, steering: str = '') -> ChatPromptTemplate:
        data_keys = self._data_input_keys()
        human_parts = []
        for key in data_keys:
            tag = self._prompt_tag(key)
            human_parts.append(f"<{tag}>\n{{{key}}}\n</{tag}>")
        system = self.prompt_template
        if steering:
            # The system prompt is a LangChain template - escape the appended
            # text so a brace in a steering line can never break every agent.
            system += '\n\n' + steering.replace('{', '{{').replace('}', '}}')
        messages = [('system', system)]
        if human_parts:
            messages.append(('human', '\n\n'.join(human_parts)))
        messages.append(MessagesPlaceholder(variable_name='messages'))
        return ChatPromptTemplate.from_messages(messages)

    async def _invoke_llm(self, complexity: str = None, repaired: bool = False, **kwargs) -> AIMessage:
        chain = self._get_chain(complexity)
        provider = self._chain_providers.get(complexity or '_default')
        # A repair re-ask is a real, billed model call - tag it so telemetry
        # can meter how often output needs repair (rides the run tags next to
        # the LLM's own `node:` tag).
        config = {'tags': [REPAIRED_TAG]} if repaired else None
        for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
            # The throttle slot is re-acquired per attempt, so retries also
            # stay within the provider's budget.
            if self.rate_limiter:
                await self.rate_limiter.wait_if_needed(provider)
            try:
                response = await asyncio.wait_for(
                    chain.ainvoke(kwargs, config=config), timeout=settings.llm_timeout
                )
                break
            except asyncio.TimeoutError:
                raise TimeoutError(
                    f"LLM call timed out after {settings.llm_timeout} seconds"
                ) from None
            except Exception as exc: # pylint: disable=broad-exception-caught
                delay = retry_delay(exc, attempt)
                if delay is None or attempt >= MAX_RATE_LIMIT_RETRIES:
                    raise
                self.logger.warning(
                    "%s rate limited (429); retrying in %.1fs (attempt %d/%d)...",
                    provider or 'Provider', delay, attempt + 1, MAX_RATE_LIMIT_RETRIES,
                )
                await asyncio.sleep(delay)
        self.logger.debug("Raw Response Content:\n%s", response.content)
        self.logger.debug("Tool Calls:\n%s", response.tool_calls)
        return response

    def _parse_outputs(self, response, state: ProjectState = None) -> T:
        if not response.tool_calls:
            raise NoToolCallError("The model did not call any tool.")
        tool_call = response.tool_calls[0]
        return self._map_tool_to_output(tool_call['name'], tool_call['args'], state)

    def _map_tool_to_output(self, tool_name: str, tool_args: dict, state: ProjectState = None) -> T:
        """Map a tool call to the agent's output schema. Raising ValidationError here re-prompts the model with the failure."""
        return self.output_schema(**tool_args)

    _MAX_INCLUDE_DEPTH: int = 10
    _INCLUDE_PATTERN = re.compile(r"\{\{\s*include\s+([\w./-]+?)(?:\s+if\s+(not\s+)?(\w+))?\s*\}\}")
    # The unified prompt-body conventions (TODO 1.3) allow a shared body to
    # carry these placeholders for the loader that renders them. This loader
    # has no renderer (tools are bound natively, skills and workspace content
    # ride the `inputs:` sections), so they are stripped - a shared body still
    # renders here, and a stray brace never reaches the LangChain template.
    _PLACEHOLDER_PATTERN = re.compile(r'\{\{\s*(tools|skills|environment)\s*\}\}')

    @classmethod
    def _resolve_includes(cls, prompt: str, base_dir: Path) -> str:
        """Replace `{{ include <name> [if [not] <setting>] }}` with the named file's body.

        The unified include syntax shared with my-dev-team-vs-code: the name is
        normalised (a leading path and a trailing .md are stripped) and resolved
        against `partials/` first, then base_dir itself (so a config can inherit a
        full agent prompt). The optional `if <setting>` / `if not <setting>` clause
        includes the block only when the named settings flag is truthy / falsy.
        Frontmatter of the included file is stripped; includes may nest up to
        _MAX_INCLUDE_DEPTH levels, which rejects cycles.
        """
        base = base_dir.resolve()
        def replacer(match):
            arg, negate, condition = match.groups()
            if condition and bool(getattr(settings, condition, False)) == bool(negate):
                return ''
            name = re.sub(r'\.md$', '', arg).split('/')[-1]
            for candidate in (base / 'partials' / f'{name}.md', base / f'{name}.md'):
                if candidate.exists():
                    text = candidate.read_text(encoding='utf-8')
                    parts = text.split('---', 2)
                    return parts[2].strip() if len(parts) >= 3 else text.strip()
            raise FileNotFoundError(f"Include '{arg}': no partial '{name}.md' in {base / 'partials'} or {base}")
        for _ in range(cls._MAX_INCLUDE_DEPTH):
            if not cls._INCLUDE_PATTERN.search(prompt):
                return prompt
            prompt = cls._INCLUDE_PATTERN.sub(replacer, prompt)
        raise ValueError(f"Include nesting exceeded {cls._MAX_INCLUDE_DEPTH} levels - most likely a cyclic include")

    @classmethod
    def from_config(cls, node_name: str, config_path: str, *, llm_factory: LLMFactory = None, rate_limiter: RateLimiter = None, capabilities: dict[str, float] | list[str] = None, temperature: float = None, top_k: int = None, top_p: float = None):
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
        prompt = cls._PLACEHOLDER_PATTERN.sub('', prompt)
        config.update({k: v for k, v in {
            'capabilities': capabilities, 'temperature': temperature, 'top_k': top_k, 'top_p': top_p,
        }.items() if v is not None})
        return cls(config, prompt, node_name, llm_factory=llm_factory, rate_limiter=rate_limiter)
