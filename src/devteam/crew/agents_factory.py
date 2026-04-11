import yaml
import devteam.agents as agents_module
from devteam import settings
import devteam.tools as tools_module
from devteam.utils import LLMFactory, RateLimiter, WithLogging

class AgentsFactory(WithLogging):
    """Factory to create agent instances based on crew configuration files."""

    def __init__(self, llm_factory: LLMFactory = None, rate_limiter: RateLimiter = None, config_dir = None):
        self.llm_factory = llm_factory
        self.rate_limiter = rate_limiter
        self.config_dir = config_dir or settings.config_dir

    def load_crew_config(self, config_name: str) -> dict:
        config_path = self.config_dir / 'crews' / config_name
        return yaml.safe_load(config_path.read_text(encoding='utf-8'))

    def create_agents(self, config_name: str) -> dict:
        crew_config = self.load_crew_config(config_name)
        return self.create_agents_from_config(crew_config)

    def create_agents_from_config(self, crew_config: dict) -> dict:
        agents = {}
        for node_name, details in crew_config.get('agents', {}).items():
            class_name = details['class']
            config_file = details['config'] if not settings.no_docker else details.get('config-no-docker', details['config'])
            AgentClass = getattr(agents_module, class_name, None) # pylint: disable=invalid-name
            if not AgentClass:
                raise ValueError(f"Configuration Error: '{class_name}' is not a valid class in devteam.agents")
            self.logger.debug("Instantiating '%s' as %s with configuration file '%s'...", node_name, class_name, config_file)
            agent = AgentClass.from_config(node_name, config_file, llm_factory=self.llm_factory, rate_limiter=self.rate_limiter)
            if sandbox_class := details.get('sandbox', None):
                if not settings.no_docker:
                    ToolsClass = getattr(tools_module, sandbox_class, None) # pylint: disable=invalid-name
                    if not ToolsClass:
                        raise ValueError(f"Configuration Error: '{sandbox_class}' is not a valid class in devteam.tools")
                    self.logger.debug("Adding %s tool to '%s'...", sandbox_class, node_name)
                    agent = agent.with_sandbox(ToolsClass())
                else:
                    self.logger.debug("Skipping sandbox for %s", class_name)
            agents[node_name] = agent
        return agents
