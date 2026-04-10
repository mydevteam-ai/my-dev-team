import fnmatch
import logging
import re
import shutil
import zipfile
from pathlib import Path
from .sanitizer import sanitize_for_prompt

MAX_RESULTS = 50

# Patterns excluded from ListFiles, GlobFiles and GrepFiles results.
EXCLUDED_PATTERNS = [
    # Secrets and environment
    '.env', '.env.*',
    # Git
    '.git/*',
    # Python
    '__pycache__/*', '*.pyc', '*.pyo', '*.pyd',
    '*.egg-info/*', 'dist/*', 'build/*',
    '.venv/*', 'venv/*', '.tox/*', '.mypy_cache/*', '.pytest_cache/*',
    # Java
    'target/*', '*.class', '*.jar', '*.war', '*.ear',
    '.gradle/*', '.idea/*',
    # JavaScript / TypeScript
    'node_modules/*', '.next/*', '.nuxt/*',
    '*.min.js', '*.min.css', '*.map',
    # General build / binary
    '*.so', '*.dll', '*.dylib', '*.exe',
    '*.whl', '*.tar.gz', '*.zip',
    '*.png', '*.jpg', '*.jpeg', '*.gif', '*.ico', '*.svg',
    '*.woff', '*.woff2', '*.ttf', '*.eot',
    '*.sqlite', '*.db',
    '.DS_Store', 'Thumbs.db',
]


def _is_excluded(path: str) -> bool:
    return any(fnmatch.fnmatch(path, pat) for pat in EXCLUDED_PATTERNS)


def live_paths(workspace_path: str) -> list[str]:
    """Return all relative file paths under the live workspace dir, excluding ignored ones."""
    if not workspace_path:
        return []
    live_root = Path(workspace_path)
    if not live_root.is_dir():
        return []
    paths: list[str] = []
    for f in live_root.rglob('*'):
        if f.is_file():
            rel = str(f.relative_to(live_root)).replace('\\', '/')
            if not _is_excluded(rel):
                paths.append(rel)
    return paths


def read_all_files(workspace_path: str) -> dict[str, str]:
    """Load every non-excluded file under the live workspace dir into a {path: content} dict."""
    result: dict[str, str] = {}
    if not workspace_path:
        return result
    live_root = Path(workspace_path)
    for rel in live_paths(workspace_path):
        result[rel] = (live_root / rel).read_text(encoding='utf-8')
    return result


def workspace_str_from_files(workspace_files: dict) -> str:
    workspace_str = ''
    for filepath, content in workspace_files.items():
        clean_content = sanitize_for_prompt(content, [filepath, 'workspace'])
        workspace_str += f"--- FILE: {filepath} ---\n{clean_content}\n\n"
    return workspace_str


def read_workspace_file(path: str, workspace_path: str) -> str:
    if _is_excluded(path):
        return f"Access denied: '{path}' is in the excluded files list."
    if workspace_path:
        live_root = Path(workspace_path).resolve()
        target = (live_root / path).resolve()
        if target.is_relative_to(live_root) and target.is_file():
            content = target.read_text(encoding='utf-8')
            return f"--- FILE: {path} ---\n{content}"
    available = list_workspace_files(workspace_path)
    return f"File not found: '{path}'. {available}"


def list_workspace_files(workspace_path: str) -> str:
    paths = sorted(live_paths(workspace_path))
    if not paths:
        return 'No files in workspace.'
    file_list = '\n'.join(f"- {p}" for p in paths)
    return f"Workspace files ({len(paths)}):\n{file_list}"


def glob_workspace_files(pattern: str, workspace_path: str) -> str:
    """Find workspace files matching a glob pattern."""
    matches = sorted(p for p in live_paths(workspace_path) if fnmatch.fnmatch(p, pattern))
    if not matches:
        return f"No files matching '{pattern}'."
    file_list = '\n'.join(f"- {p}" for p in matches[:MAX_RESULTS])
    result = f"Matching files ({len(matches)}):\n{file_list}"
    if len(matches) > MAX_RESULTS:
        result += f"\n... and {len(matches) - MAX_RESULTS} more"
    return result


def grep_workspace_files(pattern: str, workspace_path: str, glob_filter: str = None) -> str:
    """Search workspace file contents for a regex pattern."""
    try:
        regex = re.compile(pattern)
    except re.error as e:
        return f"Invalid regex pattern: {e}"
    paths = live_paths(workspace_path)
    if glob_filter:
        paths = [p for p in paths if fnmatch.fnmatch(p, glob_filter)]
    matches = []
    files_matched = set()
    live_root = Path(workspace_path) if workspace_path else None
    for path in sorted(paths):
        content = (live_root / path).read_text(encoding='utf-8')
        for i, line in enumerate(content.splitlines(), 1):
            if regex.search(line):
                matches.append(f"{path}:{i}: {line.strip()}")
                files_matched.add(path)
                if len(matches) >= MAX_RESULTS:
                    break
        if len(matches) >= MAX_RESULTS:
            break
    if not matches:
        return f"No matches for '{pattern}'."
    result = '\n'.join(matches)
    total = len(matches)
    summary = f"\n\n({total} match{'es' if total != 1 else ''} across {len(files_matched)} file{'s' if len(files_matched) != 1 else ''})"
    if total >= MAX_RESULTS:
        summary += " - results truncated"
    return result + summary


def hydrate_workspace(seed: str, live_dir: Path):
    """Populate the live workspace directory from a local directory or ZIP archive."""
    seed_path = Path(seed)
    live_dir.mkdir(parents=True, exist_ok=True)
    if seed_path.is_dir():
        shutil.copytree(seed_path, live_dir, dirs_exist_ok=True)
        logging.info('🌱 Workspace seeded from directory: %s', seed_path.absolute())
    else:
        with zipfile.ZipFile(seed_path, 'r') as zf:
            zf.extractall(live_dir)
        logging.info('🌱 Workspace seeded from archive: %s', seed_path.absolute())
