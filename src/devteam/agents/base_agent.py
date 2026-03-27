import asyncio
from functools import cached_property
import traceback
import yaml
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable
from pydantic import BaseModel
from devteam import settings
from devteam.skills import skills
from devteam.utils import LLMFactory, RateLimiter, WithLogging, CommunicationLog
from devteam.utils.sanitizer import sanitize_for_prompt
from .schemas import LoadSkill

class BaseAgent[T: BaseModel](CommunicationLog, WithLogging):
    """Base agent that uses LLM tool calling to submit structured results."""

    model_category: str = 'reasoning'
    temperature: float = 0.2
    max_retries: int = 2
    rate_limiter: RateLimiter = None
    output_schema: type[T]
    tools: list[type[BaseModel]]

    def __init__(self, config: dict, prompt_template: str, node_name: str, llm_factory: LLMFactory = None, rate_limiter: RateLimiter = None):
        self.config = config
        self.prompt_template = prompt_template
        self.node_name = node_name
        self.llm_factory = llm_factory
        self.rate_limiter = rate_limiter
        self.role = config.get('role', 'Agent')
        self.name = config.get('name', None)
        self.model_category = config.get('model', self.model_category)
        self.temperature = config.get('temperature', self.temperature)

    @staticmethod
    def sanitize_for_prompt(content: str, tags: list[str] | str = None) -> str:
        return sanitize_for_prompt(content, tags)

    @cached_property
    def inputs(self) -> list[str]:
        return self.config.get('inputs', [])

    @cached_property
    def outputs(self) -> list[str]:
        return self.config.get('outputs', [])

    def _build_inputs(self, state: dict) -> dict:
        inputs = {}
        for key in self.inputs:
            val = state.get(key, '')
            if key == 'messages': # Do not sanitize messages
                inputs[key] = val
            elif key == 'skills':
                inputs[key] = self.sanitize_for_prompt(self.skills_catalog, 'skills')
            else:
                inputs[key] = self.sanitize_for_prompt(str(val), key) if val else ''
        return inputs

    def _update_state(self, parsed_data: T, current_state: dict) -> dict:
        return parsed_data.model_dump()

    async def _pre_process(self, state: dict) -> dict:
        """Lifecycle Hook: performs actions BEFORE the LLM runs."""
        return state

    async def _post_process(self, state: dict, final_state: dict) -> dict:
        """Lifecycle Hook: performs actions AFTER the LLM runs."""
        return final_state

    def _handle_intermediate_tools(self, tool_name: str, tool_args: dict) -> str | None:
        """Handle intermediate tool calls that are not final outputs, e.g. LoadSkill."""
        match tool_name:
            case 'LoadSkill':
                skill_name = tool_args.get('skill_name')
                skill_content = skills.load_skill(skill_name)
                self.logger.info(f"Loaded skill: {skill_name}. LLM is re-evaluating...")
                self.logger.debug(f"\n--- Skill Content Start ---\n{skill_content[:1000]}\n--- Skill Content End ---")
                return skill_content
        return None

    async def process(self, state: dict) -> dict:
        """Invoke LLM and use tools to provide structured results."""
        self.logger.info("Executing...")
        state = await self._pre_process(state)
        inputs = self._build_inputs(state)
        conversation_history = []
        try:
            while True:
                if conversation_history:
                    inputs['messages'] = inputs.get('messages', []) + conversation_history
                self.logger.debug("Invoking LLM with inputs:\n%s", inputs)
                ai_message = await self._invoke_llm(**inputs)
                conversation_history.append(ai_message)
                if not ai_message.tool_calls:
                    raise ValueError("The model did not call any tool.")
                tool_call = ai_message.tool_calls[0]
                if intermediate_result := self._handle_intermediate_tools(tool_call['name'], tool_call['args']):
                    tool_msg = ToolMessage(content=intermediate_result, tool_call_id=tool_call['id'])
                    conversation_history.append(tool_msg)
                    continue
                parsed_data = self._parse_outputs(ai_message)
                break
        except Exception: # pylint: disable=broad-exception-caught
            full_traceback = traceback.format_exc()
            return {
                'error': True,
                'error_message': full_traceback,
            }
        final_state = self._update_state(parsed_data, state)
        final_state = await self._post_process(state, final_state)
        if 'messages' in self.outputs:
            final_state['messages'] = conversation_history
        final_state['communication_log'] = self.communication(ai_message.content)
        return final_state

    @cached_property
    def skills_catalog(self) -> str:
        if catalog := skills.load_skills_catalog():
            return '\n'.join(f"- `{item['name']}`: {item['description']}" for item in catalog)
        return "No skills available."

    @cached_property
    def all_tools(self) -> list[type[BaseModel]]:
        return [LoadSkill] + (self.tools or [])

    @cached_property
    def llm(self) -> Runnable:
        llm = self.llm_factory.create(
            category=self.model_category,
            temperature=self.temperature,
            node_name=self.node_name,
            json_mode=False
        )
        return llm.bind_tools(self.all_tools)

    def _build_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages([
            ('system', self.prompt_template),
            MessagesPlaceholder(variable_name='messages', optional=True)
        ])

    @cached_property
    def chain(self) -> Runnable:
        return self._build_prompt() | self.llm

    async def _invoke_llm(self, **kwargs) -> AIMessage:
        if self.rate_limiter:
            await self.rate_limiter.wait_if_needed()
        try:
            response = await asyncio.wait_for(
                self.chain.ainvoke(kwargs), timeout=settings.llm_timeout
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

    @classmethod
    def from_config(cls, node_name: str, config_path: str, *, llm_factory: LLMFactory = None, rate_limiter: RateLimiter = None, model_category: str = None, temperature: float = None):
        prompt_file = settings.config_dir / 'agents' / config_path
        try:
            content = prompt_file.read_text(encoding='utf-8')
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Could not find agent prompt '{config_path}' in {prompt_file.parent}") from e
        parts = content.split('---', 2)
        if len(parts) < 3:
            raise ValueError(f"Invalid format in {config_path}. Missing YAML frontmatter")
        config = yaml.safe_load(parts[1])
        prompt = parts[2].strip()
        if model_category is not None:
            config['model'] = model_category
        if temperature is not None:
            config['temperature'] = temperature
        return cls(config, prompt, node_name, llm_factory=llm_factory, rate_limiter=rate_limiter)
