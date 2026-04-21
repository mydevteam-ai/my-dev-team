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

    def _select_model(self, capabilities: dict[str, float], complexity: str = None) -> dict:
        """Select the best model entry for the requested capabilities using weighted scoring."""
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

    def _instantiate(self, model: dict, provider: str, temperature: float, *, node_name: str, json_mode: bool, thinking_override: bool = None) -> BaseChatModel:
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
                    reasoning=thinking and settings.llm_streaming and not json_mode
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
                    max_retries=2
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
                    tags=llm_tags
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
                    tags=llm_tags
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
                    tags=llm_tags
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
                    tags=llm_tags
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
                    base_url='https://api.deepseek.com'
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
                    base_url='https://api.x.ai/v1'
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
                    tags=llm_tags
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
                    tags=llm_tags
                )
            case _:
                raise ValueError(f"Unsupported provider: {provider}")

    def create(self, capabilities: dict[str, float] | list[str], temperature: float, *,
               node_name: str, json_mode = True, complexity: str | None = None,
               thinking: bool | None = None) -> BaseChatModel:
        """Returns a configured LLM instance for the requested capabilities."""
        if isinstance(capabilities, list):
            capabilities = {cap: 1.0 for cap in capabilities}
        model = self._select_model(capabilities, complexity=complexity)
        provider = model.get('provider', self.provider)
        if complexity:
            self.logger.debug(
                "Complexity routing: node=%s complexity=%s -> provider=%s model=%s",
                node_name, complexity, provider, model['id']
            )
        return self._instantiate(model, provider, temperature, node_name=node_name, json_mode=json_mode, thinking_override=thinking)
