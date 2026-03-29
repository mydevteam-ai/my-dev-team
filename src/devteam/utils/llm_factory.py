from functools import cached_property
import yaml
from langchain_core.language_models.chat_models import BaseChatModel
from devteam import settings

class LLMFactory:
    def __init__(self, provider: str, callbacks: list = None):
        self.provider = provider.lower()
        self.callbacks = callbacks or []
        if self.provider not in self.model_map:
            raise ValueError(f"Unsupported provider: {self.provider}")

    @cached_property
    def llm_config(self) -> dict:
        config_path = settings.config_dir / 'llms.yaml'
        return yaml.safe_load(config_path.read_text(encoding='utf-8'))

    @cached_property
    def model_map(self) -> dict:
        return self.llm_config.get('providers', {})

    def _select_model(self, capabilities: dict[str, float]) -> dict:
        """Select the best model entry for the requested capabilities using weighted scoring."""
        models = self.model_map[self.provider]['models']
        total_weight = sum(capabilities.values()) or 1.0
        best_model = models[0]
        best_score = -1.0
        for model in models:
            model_caps = model.get('capabilities', {})
            score = sum(
                weight * model_caps.get(cap, 0.0)
                for cap, weight in capabilities.items()
            ) / total_weight
            if score > best_score:
                best_score = score
                best_model = model
        return best_model

    def create(self, capabilities: dict[str, float] | list[str], temperature: float, *, node_name: str, json_mode = True) -> BaseChatModel:
        """Returns a configured LLM instance for the requested capabilities."""
        # pylint: disable=import-error,import-outside-toplevel
        if isinstance(capabilities, list):
            capabilities = {cap: 1.0 for cap in capabilities}
        model = self._select_model(capabilities)
        model_name = model['id']
        streaming = settings.llm_streaming
        node_tag = f'node:{node_name}'
        llm_tags = [node_tag]
        match self.provider:
            case 'ollama':
                try:
                    from langchain_ollama import ChatOllama
                except ImportError:
                    raise ImportError("Missing package for Ollama provider. Install it with: pip install langchain-ollama") from None
                thinking = model.get('thinking', True)
                return ChatOllama(
                    model=model_name,
                    temperature=temperature,
                    streaming=streaming,
                    callbacks=self.callbacks,
                    tags=llm_tags,
                    format='json' if json_mode else None,
                    reasoning=thinking and streaming and not json_mode
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
            case _:
                raise ValueError(f"Unsupported provider: {self.provider}")
