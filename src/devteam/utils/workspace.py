from pathlib import Path
from .sanitizer import sanitize_for_prompt

def workspace_str_from_files(workspace_files: dict) -> str:
    workspace_str = ''
    for filepath, content in workspace_files.items():
        clean_content = sanitize_for_prompt(content, [filepath, 'workspace'])
        workspace_str += f"--- FILE: {filepath} ---\n{clean_content}\n\n"
    return workspace_str


def read_workspace_file(path: str, workspace_files: dict, workspace_path: str) -> str:
    if path in workspace_files:
        return f"--- FILE: {path} ---\n{workspace_files[path]}"
    if workspace_path:
        live_root = Path(workspace_path).resolve()
        target = (live_root / path).resolve()
        if target.is_relative_to(live_root) and target.is_file():
            content = target.read_text(encoding='utf-8')
            return f"--- FILE: {path} ---\n{content}"
    available = list_workspace_files(workspace_files, workspace_path)
    return f"File not found: '{path}'. {available}"


def list_workspace_files(workspace_files: dict, workspace_path: str) -> str:
    paths = set(workspace_files.keys())
    if workspace_path:
        live_root = Path(workspace_path)
        if live_root.is_dir():
            for f in live_root.rglob('*'):
                if f.is_file():
                    paths.add(str(f.relative_to(live_root)).replace('\\', '/'))
    if not paths:
        return 'No files in workspace.'
    file_list = '\n'.join(f"- {p}" for p in sorted(paths))
    return f"Workspace files ({len(paths)}):\n{file_list}"
