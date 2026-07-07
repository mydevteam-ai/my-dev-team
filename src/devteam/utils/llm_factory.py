from functools import cached_property
import os
import yaml
from langchain_core.language_models.chat_models import BaseChatModel
from devteam import settings
from .with_logging import WithLogging

def get_valid_providers() -> list[str]:
    """Return provider names defined in the active llms.yaml."""
    try:
        config_path = settings.tools_config_dir / 'llms.yaml'
        config = yaml.safe_load(config_path.read_text(encoding='utf-8'))
        return list((config or {}).get('providers', {}).keys())
    except Exception:
        return []

class LLMFactory(WithLogging):
    def __init__(self, provider: str, callbacks: list = None):
        self.provider = provider.lower()
        self.callbacks = callbacks or []
        if self.provider not in self.model_map:
            raise ValueError(f"Unsupported provider: {self.provider}")

    @cached_property
    def llm_config(self) -> dict:
        config_path = settings.tools_config_dir / 'llms.yaml'
        return yaml.safe_load(config_path.read_text(encoding='utf-8'))

    @cached_property
    def model_map(self) -> dict:
        return self.llm_config.get('providers', {})

    @cached_property
    def provider_rpm_defaults(self) -> dict[str, int]:
        """Per-provider default request budgets (requests per minute) from
        llms.yaml - the shared registry's `providers:` rpm seeds. Keyed by
        real provider name; a provider without an `rpm` key has no default
        throttle. Consumed by RateLimiter, where the user's --rpm override
        wins over every default."""
        return {name: int(section.get('rpm', 0) or 0) for name, section in self.model_map.items()}

    def select_model(self, capabilities: dict[str, float] | list[str], complexity: str = None) -> dict:
        """Select the best model entry for the requested capabilities using weighted scoring.

        Public so a caller can inspect the routed entry (e.g. derive prompt
        steering from its capability scores) and hand it back to `create()`
        via `model=` - selection then happens exactly once and steering and
        instantiation can never disagree about the routed model.
        """
        if isinstance(capabilities, list):
            capabilities = {cap: 1.0 for cap in capabilities}
        models = self.model_map[self.provider]['models']
        total_weight = sum(capabilities.values()) or 1.0
        best_model = models[0]
        best_score = -1.0
        for model in models:
            model_caps = model.get('capabilities', {})
            cap_score = sum(
                weight * model_caps.get(cap, 0.0)
                for cap, weight in capabilities.items()
            ) / total_weight
            if complexity:
                fit = model.get('complexity_fit', {}).get(complexity, 1.0)
                score = cap_score * fit
            else:
                score = cap_score
            if score > best_score:
                best_score = score
                best_model = model
        return best_model

    def _instantiate(self, model: dict, provider: str, temperature: float, *, node_name: str, json_mode: bool, thinking_override: bool = None, top_k: int = None, top_p: float = None) -> BaseChatModel:
        """Instantiate a provider-specific LLM for the given model entry."""
        # pylint: disable=import-error,import-outside-toplevel
        model_name = model['id']
        llm_tags = [f'node:{node_name}']
        match provider:
            case 'ollama':
                try:
                    from langchain_ollama import ChatOllama
                except ImportError:
                    raise ImportError("Missing package for Ollama provider. Install it with: pip install langchain-ollama") from None
                thinking = thinking_override if thinking_override is not None else model.get('thinking', True)
                return ChatOllama(
                    model=model_name,
                    temperature=temperature,
                    streaming=settings.llm_streaming,
                    callbacks=self.callbacks,
                    tags=llm_tags,
                    format='json' if json_mode else None,
                    reasoning=thinking and settings.llm_streaming and not json_mode,
                    **({'top_k': top_k} if top_k is not None else {}),
                    **({'top_p': top_p} if top_p is not None else {}),
                )
            case 'groq':
                try:
                    from langchain_groq import ChatGroq
                except ImportError:
                    raise ImportError("Missing package for Groq provider. Install it with: pip install langchain-groq") from None
                llm = ChatGroq(
                    model=model_name,
                    temperature=temperature,
                    streaming=settings.llm_streaming,
                    callbacks=self.callbacks,
                    tags=llm_tags,
                    max_retries=2,
                    **({'model_kwargs': {'top_p': top_p}} if top_p is not None else {}),
                )
                if json_mode:
                    return llm.bind(response_format={'type': 'json_object'})
                return llm
            case 'anthropic':
                try:
                    from langchain_anthropic import ChatAnthropic
                except ImportError:
                    raise ImportError("Missing package for Anthropic provider. Install it with: pip install langchain-anthropic") from None
                return ChatAnthropic(
                    model=model_name,
                    temperature=temperature,
                    streaming=settings.llm_streaming,
                    callbacks=self.callbacks,
                    tags=llm_tags,
                    **({'top_k': top_k} if top_k is not None else {}),
                    **({'top_p': top_p} if top_p is not None else {}),
                )
            case 'openai':
                try:
                    from langchain_openai import ChatOpenAI
                except ImportError:
                    raise ImportError("Missing package for OpenAI provider. Install it with: pip install langchain-openai") from None
                return ChatOpenAI(
                    model=model_name,
                    temperature=temperature,
                    streaming=settings.llm_streaming,
                    callbacks=self.callbacks,
                    tags=llm_tags,
                    **({'top_p': top_p} if top_p is not None else {}),
                )
            case 'google':
                try:
                    from langchain_google_genai import ChatGoogleGenerativeAI
                except ImportError:
                    raise ImportError("Missing package for Google provider. Install it with: pip install langchain-google-genai") from None
                return ChatGoogleGenerativeAI(
                    model=model_name,
                    temperature=temperature,
                    streaming=settings.llm_streaming,
                    callbacks=self.callbacks,
                    tags=llm_tags,
                    **({'top_k': top_k} if top_k is not None else {}),
                    **({'top_p': top_p} if top_p is not None else {}),
                )
            case 'mistral':
                try:
                    from langchain_mistralai import ChatMistralAI
                except ImportError:
                    raise ImportError("Missing package for Mistral provider. Install it with: pip install langchain-mistralai") from None
                return ChatMistralAI(
                    model=model_name,
                    temperature=temperature,
                    streaming=settings.llm_streaming,
                    callbacks=self.callbacks,
                    tags=llm_tags,
                    **({'top_p': top_p} if top_p is not None else {}),
                )
            case 'deepseek':
                try:
                    from langchain_openai import ChatOpenAI
                except ImportError:
                    raise ImportError("Missing package for DeepSeek provider. Install it with: pip install langchain-openai") from None
                return ChatOpenAI(
                    model=model_name,
                    temperature=temperature,
                    streaming=settings.llm_streaming,
                    callbacks=self.callbacks,
                    tags=llm_tags,
                    api_key=os.environ['DEEPSEEK_API_KEY'],
                    base_url='https://api.deepseek.com',
                    **({'top_p': top_p} if top_p is not None else {}),
                )
            case 'zai':
                try:
                    from langchain_openai import ChatOpenAI
                except ImportError:
                    raise ImportError("Missing package for Z.AI provider. Install it with: pip install langchain-openai") from None
                return ChatOpenAI(
                    model=model_name,
                    temperature=temperature,
                    streaming=settings.llm_streaming,
                    callbacks=self.callbacks,
                    tags=llm_tags,
                    api_key=os.environ['ZAI_API_KEY'],
                    base_url='https://api.z.ai/api/paas/v4',
                    **({'top_p': top_p} if top_p is not None else {}),
                )
            case 'grok':
                try:
                    from langchain_openai import ChatOpenAI
                except ImportError:
                    raise ImportError("Missing package for xAI/Grok provider. Install it with: pip install langchain-openai") from None
                return ChatOpenAI(
                    model=model_name,
                    temperature=temperature,
                    streaming=settings.llm_streaming,
                    callbacks=self.callbacks,
                    tags=llm_tags,
                    api_key=os.environ['XAI_API_KEY'],
                    base_url='https://api.x.ai/v1',
                    **({'top_p': top_p} if top_p is not None else {}),
                )
            case 'azure-openai':
                try:
                    from langchain_openai import AzureChatOpenAI
                except ImportError:
                    raise ImportError("Missing package for Azure OpenAI provider. Install it with: pip install langchain-openai") from None
                return AzureChatOpenAI(
                    azure_deployment=os.environ.get('AZURE_OPENAI_DEPLOYMENT', model_name),
                    api_version=os.environ.get('AZURE_OPENAI_API_VERSION', '2024-08-01-preview'),
                    azure_endpoint=os.environ['AZURE_OPENAI_ENDPOINT'],
                    api_key=os.environ['AZURE_OPENAI_API_KEY'],
                    temperature=temperature,
                    streaming=settings.llm_streaming,
                    callbacks=self.callbacks,
                    tags=llm_tags,
                    **({'top_p': top_p} if top_p is not None else {}),
                )
            case 'azure-anthropic':
                try:
                    from langchain_openai import ChatOpenAI
                except ImportError:
                    raise ImportError("Missing package for Azure Claude provider. Install it with: pip install langchain-openai") from None
                return ChatOpenAI(
                    model=model_name,
                    base_url=os.environ['AZURE_ANTHROPIC_ENDPOINT'],
                    api_key=os.environ['AZURE_ANTHROPIC_API_KEY'],
                    temperature=temperature,
                    streaming=settings.llm_streaming,
                    callbacks=self.callbacks,
                    tags=llm_tags,
                    **({'top_p': top_p} if top_p is not None else {}),
                )
            case _:
                raise ValueError(f"Unsupported provider: {provider}")

    def create(self, capabilities: dict[str, float] | list[str], temperature: float, *,
               node_name: str, json_mode = True, complexity: str = None,
               thinking: bool = None, top_k: int = None, top_p: float = None,
               model: dict = None) -> BaseChatModel:
        """Returns a configured LLM instance for the requested capabilities.

        `model` may carry an entry pre-selected via `select_model()` to skip
        re-selection; when omitted, the best-fit entry is selected here.
        """
        model = model or self.select_model(capabilities, complexity=complexity)
        provider = model.get('provider', self.provider)
        if complexity:
            self.logger.debug(
                "Complexity routing: node=%s complexity=%s -> provider=%s model=%s",
                node_name, complexity, provider, model['id']
            )
        return self._instantiate(model, provider, temperature, node_name=node_name, json_mode=json_mode, thinking_override=thinking, top_k=top_k, top_p=top_p)
