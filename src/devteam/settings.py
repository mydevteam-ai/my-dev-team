from functools import cached_property
from pathlib import Path
import yaml

USER_CONFIG_PATH = Path.home() / 'config.yaml'

class Settings:
    workspace_dir: Path = Path('workspaces')
    config_dir: Path = Path(__file__).parent / 'config'
    skills_dir: Path = Path('skills')
    llm_timeout: int = 120  # seconds
    llm_streaming: bool = False
    provider: str = 'ollama'
    rpm: int = 0
    no_docker: bool = False
    ask_approval: bool = False
    rag_mcp_url: str = 'http://localhost:8000/mcp'
    rag_mcp_tool: str = 'qdrant-find'
    rag_collection: str = None
    rag_enabled: bool = True
    max_revision_count: int = 3

    @cached_property
    def tools_config_dir(self) -> Path:
        return self.config_dir / 'tools'

    _INTERNAL = {'config_dir'}
    _COERCE = {Path: lambda v: Path(v).expanduser(), int: int, bool: bool, str: str}

    def load(self, config_path: Path = USER_CONFIG_PATH) -> None:
        if not config_path.exists():
            return
        with open(config_path) as f:
            cfg = yaml.safe_load(f) or {}
        hints = type(self).__annotations__
        for key, value in cfg.items():
            if key in self._INTERNAL:
                continue
            if key in hints:
                setattr(self, key, self._COERCE.get(hints[key], str)(value))

settings = Settings()
