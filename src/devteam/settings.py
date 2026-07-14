from functools import cached_property
from pathlib import Path
import re
import yaml


class Coerced:
    """Descriptor that coerces values to a target type on assignment."""

    def __init__(self, default, type_ = None, *, cli = None, cli_invert = False):
        self.type_ = type_ or type(default)
        self.default = self._maybe_coerce(default)
        self._cli = cli
        self.cli_invert = cli_invert

    @property
    def cli_arg(self):
        """Resolved CLI arg name, or None if this attribute has no CLI mapping."""
        if self._cli is None:
            return None
        return self.attr[1:] if self._cli is True else self._cli

    def __set_name__(self, owner, name):
        self.attr = '_' + name

    def __get__(self, obj, objtype = None):
        if obj is None:
            return self
        return getattr(obj, self.attr, self.default)

    def __set__(self, obj, value):
        setattr(obj, self.attr, self._maybe_coerce(value))

    def _maybe_coerce(self, value):
        if value is None or isinstance(value, self.type_):
            return value
        return self._coerce(value)

    def _coerce(self, value):
        return self.type_(value)


class CoercedPath(Coerced):
    """Path-typed Coerced that runs expanduser() on coercion."""

    def __init__(self, default, **kwargs):
        super().__init__(default, Path, **kwargs)

    def _coerce(self, value):
        return Path(value).expanduser()


_LOCAL_CONFIG_PATH = Path('config.yaml')
_GLOBAL_CONFIG_PATH = Path.home() / '.devteam' / 'config.yaml'


class Settings:
    config_dir: Path = Path(__file__).parent / 'config'

    workspace_dir = CoercedPath('workspaces')
    skills_dir = CoercedPath('skills', cli='skills')
    llm_timeout = Coerced(120)
    llm_streaming = Coerced(False)
    provider = Coerced('ollama')
    rpm = Coerced(0)
    no_docker = Coerced(False, cli=True)
    ask_approval = Coerced(False, cli=True)
    ask_all = Coerced(False, cli=True)
    rag_mcp_url = Coerced('http://localhost:8000/mcp')
    rag_mcp_tool = Coerced('qdrant-find')
    rag_collection = Coerced(None, str, cli=True)
    rag_enabled = Coerced(True, cli='no_rag', cli_invert=True)
    max_revision_count = Coerced(3, cli='max_revisions')
    no_ask = Coerced(False, cli=True)
    no_complexity_routing = Coerced(False, cli=True)
    console = Coerced(False, cli=True)
    run_log = Coerced(True)

    @cached_property
    def tools_config_dir(self) -> Path:
        return self.config_dir / 'tools'

    def apply_args(self, args) -> None:
        for attr, descriptor in vars(type(self)).items():
            cli_arg = getattr(descriptor, 'cli_arg', None)
            if not cli_arg:
                continue
            arg_val = getattr(args, cli_arg, None)
            if arg_val:
                setattr(self, attr, not arg_val if descriptor.cli_invert else arg_val)

    def load(self, config_path: Path = None) -> None:
        paths = [config_path] if config_path else [_GLOBAL_CONFIG_PATH, _LOCAL_CONFIG_PATH]
        fields = {name for name, attr in vars(type(self)).items() if isinstance(attr, Coerced)}
        for path in paths:
            if not path.exists():
                continue
            with open(path) as f:
                cfg = yaml.safe_load(f) or {}
            for key, value in cfg.items():
                normalized = re.sub(r' +', '_', key.lower())
                if normalized in fields:
                    setattr(self, normalized, value)


settings = Settings()
