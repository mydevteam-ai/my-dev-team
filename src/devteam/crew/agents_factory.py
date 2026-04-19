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
            agent = AgentClass.from_config(
                node_name, config_file,
                llm_factory=self.llm_factory,
                rate_limiter=self.rate_limiter,
                capabilities=details.get('capabilities'),
                temperature=details.get('temperature')
            )
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

    @staticmethod
    def fanout_transform(crew_config: dict) -> dict:
        """Replace the developer node with developer_a, developer_b and judge."""
        agents = crew_config.get('agents', {})
        if 'developer' not in agents or 'developer_a' in agents:
            return crew_config
        dev = agents['developer']
        fanout_cfg = crew_config.get('fanout', {})
        dev_b_overrides = fanout_cfg.get('developer_b', {})
        judge_cfg = fanout_cfg.get('judge', {'class': 'CodeJudge', 'config': 'code-judge.md'})
        replacing = 'config' in dev_b_overrides or 'class' in dev_b_overrides
        if not replacing:
            if 'capabilities' not in dev_b_overrides:
                caps = dev.get('capabilities', ['code-generation'])
                caps_b = {c: 1.0 for c in caps} if isinstance(caps, list) else dict(caps)
                caps_b['reasoning'] = max(float(caps_b.get('reasoning', 0.0)), 1.0)
                dev_b_overrides = {**dev_b_overrides, 'capabilities': caps_b}
            if 'temperature' not in dev_b_overrides:
                base_temp = float(dev.get('temperature', 0.1))
                dev_b_overrides = {**dev_b_overrides, 'temperature': min(base_temp * 2, 1.0)}
        new_agents = {}
        for key, val in agents.items():
            if key == 'developer':
                new_agents['developer_a'] = dict(dev)
                new_agents['developer_b'] = {**dev, **dev_b_overrides}
                new_agents['judge'] = judge_cfg
            else:
                new_agents[key] = val
        return {**crew_config, 'agents': new_agents}
