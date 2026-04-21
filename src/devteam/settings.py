from functools import cached_property
from pathlib import Path
import re
import yaml

_LOCAL_CONFIG_PATH = Path('config.yaml')
_GLOBAL_CONFIG_PATH = Path.home() / '.devteam' / 'config.yaml'

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
    no_ask: bool = False
    no_complexity_routing: bool = False

    @cached_property
    def tools_config_dir(self) -> Path:
        return self.config_dir / 'tools'

    _INTERNAL = {'config_dir'}
    _COERCE = {Path: lambda v: Path(v).expanduser(), int: int, bool: bool, str: str}

    def load(self, config_path: Path = None) -> None:
        paths = [config_path] if config_path else [_GLOBAL_CONFIG_PATH, _LOCAL_CONFIG_PATH]
        hints = type(self).__annotations__
        for path in paths:
            if not path.exists():
                continue
            with open(path) as f:
                cfg = yaml.safe_load(f) or {}
            for key, value in cfg.items():
                normalized = re.sub(r' +', '_', key.lower())
                if normalized in self._INTERNAL:
                    continue
                if normalized in hints:
                    setattr(self, normalized, self._COERCE.get(hints[normalized], str)(value))

settings = Settings()
