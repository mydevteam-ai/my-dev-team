from pathlib import Path
from langgraph.checkpoint.memory import MemorySaver
from devteam.managers import ProjectManager
from devteam.utils import LLMFactory, RateLimiter, WithLogging
from .agents_factory import AgentsFactory
from .crew import VirtualCrew

class CrewFactory(WithLogging):
    BASIC_CREW = 'basic.yaml'

    def __init__(self, llm_factory: LLMFactory = None, agents_factory: AgentsFactory = None, rate_limiter: RateLimiter = None):
        self.rate_limiter = rate_limiter
        self.llm_factory = llm_factory or self._default_llm_factory()
        self.agents_factory = agents_factory or self._default_agents_factory()

    def _default_agents_factory(self):
        return AgentsFactory(llm_factory=self.llm_factory, rate_limiter=self.rate_limiter)

    @classmethod
    def _default_llm_factory(cls):
        return LLMFactory(provider='ollama')

    def create(self, project_folder: Path, *, checkpointer = None, rpm: int = 0, extensions: list = None, config_name: str = None):
        rate_limiter = self.rate_limiter or (RateLimiter(requests_per_minute=rpm) if rpm > 0 else None)
        self.agents_factory.rate_limiter = rate_limiter
        agents = self.agents_factory.create_agents(config_name or self.BASIC_CREW)
        return VirtualCrew(
            project_folder,
            manager=ProjectManager(agents),
            checkpointer=checkpointer or MemorySaver(),
            extensions=extensions or [],
        )
