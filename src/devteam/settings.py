from pathlib import Path

class Settings:
    workspace_dir: Path = Path('workspaces')
    config_dir: Path = Path(__file__).parent / 'config'
    skills_dir: Path = config_dir / 'skills'
    llm_timeout: int = 120  # seconds
    llm_streaming: bool = False
    no_docker: bool = False
    ask_approval: bool = False

settings = Settings()
