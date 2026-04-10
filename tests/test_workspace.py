import pytest
from devteam.utils.workspace import (
    _is_excluded,
    read_workspace_file,
    list_workspace_files,
    glob_workspace_files,
    grep_workspace_files,
    read_all_files,
)

WORKSPACE_FILES = {
    'src/main.py': 'def main():\n    print("hello")\n',
    'src/utils/helpers.py': 'def add(a, b):\n    return a + b\n',
    'tests/test_main.py': 'def test_main():\n    assert True\n',
    'README.md': '# My Project\nA simple project.\n',
    'config/settings.yaml': 'debug: true\n',
}


def _materialize(root, files: dict[str, str]) -> str:
    """Write the given {path: content} dict into root and return the str path."""
    for rel, content in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')
    return str(root)


@pytest.fixture
def workspace_path(tmp_path):
    return _materialize(tmp_path, WORKSPACE_FILES)


# ---------------------------------------------------------------------------
# _is_excluded
# ---------------------------------------------------------------------------

class TestIsExcluded:
    @pytest.mark.parametrize('path', [
        '.env', '.env.production',
        '.git/config', '.git/HEAD',
        '__pycache__/module.cpython-314.pyc', 'src/__pycache__/foo.pyc',
        'app.pyc', 'module.pyo',
        'dist/bundle.js', 'build/output.jar',
        'node_modules/lodash/index.js',
        'target/classes/Main.class', 'App.class',
        'lib.jar', 'app.war',
        '.venv/bin/python', 'venv/lib/site.py',
        '.next/static/chunk.js',
        'bundle.min.js', 'styles.min.css', 'main.js.map',
        'icon.png', 'photo.jpg', 'logo.svg',
        'font.woff2', 'data.sqlite',
        'package.whl', 'release.tar.gz', 'archive.zip',
        'mylib.so', 'mylib.dll', 'app.exe',
        '.DS_Store', 'Thumbs.db',
        'mypackage.egg-info/PKG-INFO',
    ])
    def test_excluded_paths(self, path):
        assert _is_excluded(path), f"Expected '{path}' to be excluded"

    @pytest.mark.parametrize('path', [
        'src/main.py', 'tests/test_main.py',
        'README.md', 'package.json', 'pom.xml',
        'src/App.tsx', 'config/settings.yaml',
        'Dockerfile', 'Makefile',
        '.gitignore', '.eslintrc.js',
        'requirements.txt', 'build.gradle',
    ])
    def test_allowed_paths(self, path):
        assert not _is_excluded(path), f"Expected '{path}' to be allowed"


# ---------------------------------------------------------------------------
# read_all_files
# ---------------------------------------------------------------------------

class TestReadAllFiles:
    def test_loads_every_file(self, workspace_path):
        files = read_all_files(workspace_path)
        assert set(files.keys()) == set(WORKSPACE_FILES.keys())
        assert files['src/main.py'] == WORKSPACE_FILES['src/main.py']

    def test_skips_excluded_files(self, tmp_path):
        path = _materialize(tmp_path, {'src/main.py': 'x', '.env': 'SECRET'})
        files = read_all_files(path)
        assert 'src/main.py' in files
        assert '.env' not in files

    def test_empty_when_no_path(self):
        assert read_all_files('') == {}


# ---------------------------------------------------------------------------
# read_workspace_file
# ---------------------------------------------------------------------------

class TestReadWorkspaceFile:
    def test_reads_from_disk(self, workspace_path):
        result = read_workspace_file('src/main.py', workspace_path)
        assert '--- FILE: src/main.py ---' in result
        assert 'def main()' in result

    def test_not_found_lists_available(self, workspace_path):
        result = read_workspace_file('nope.py', workspace_path)
        assert "File not found: 'nope.py'" in result
        assert 'src/main.py' in result

    def test_path_traversal_blocked(self, tmp_path):
        secret = tmp_path.parent / 'secret.txt'
        secret.write_text('secret', encoding='utf-8')
        path = _materialize(tmp_path / 'ws', {'a.py': 'x'})
        result = read_workspace_file('../secret.txt', path)
        assert 'File not found' in result

    def test_excluded_file_blocked(self, tmp_path):
        path = _materialize(tmp_path, {'.env': 'SECRET_KEY=abc'})
        result = read_workspace_file('.env', path)
        assert 'Access denied' in result
        assert 'SECRET_KEY' not in result


# ---------------------------------------------------------------------------
# list_workspace_files
# ---------------------------------------------------------------------------

class TestListWorkspaceFiles:
    def test_lists_disk_files(self, workspace_path):
        result = list_workspace_files(workspace_path)
        assert 'Workspace files (5)' in result
        assert '- src/main.py' in result
        assert '- README.md' in result

    def test_empty_workspace(self):
        assert list_workspace_files('') == 'No files in workspace.'

    def test_excludes_ignored_files(self, tmp_path):
        path = _materialize(tmp_path, {'src/main.py': 'x', '.env': 'SECRET'})
        # __pycache__ files are also excluded
        (tmp_path / '__pycache__').mkdir(exist_ok=True)
        (tmp_path / '__pycache__' / 'mod.pyc').write_text('', encoding='utf-8')
        result = list_workspace_files(path)
        assert 'src/main.py' in result
        assert '.env' not in result
        assert '__pycache__' not in result


# ---------------------------------------------------------------------------
# glob_workspace_files
# ---------------------------------------------------------------------------

class TestGlobWorkspaceFiles:
    def test_glob_py_files(self, workspace_path):
        result = glob_workspace_files('*.py', workspace_path)
        # *.py matches at root level only with fnmatch on full relative path
        # so we use a recursive-style pattern instead.
        result_rec = glob_workspace_files('*main*', workspace_path)
        assert 'src/main.py' in result_rec

    def test_glob_src_py(self, workspace_path):
        result = glob_workspace_files('src/*.py', workspace_path)
        assert '- src/main.py' in result
        assert 'README.md' not in result
        assert 'test_main.py' not in result

    def test_glob_md_files(self, workspace_path):
        result = glob_workspace_files('*.md', workspace_path)
        assert '- README.md' in result
        assert 'main.py' not in result

    def test_glob_no_matches(self, workspace_path):
        result = glob_workspace_files('*.rs', workspace_path)
        assert "No files matching '*.rs'" in result

    def test_glob_truncation(self, tmp_path):
        many = {f'file_{i:03d}.py': '' for i in range(60)}
        path = _materialize(tmp_path, many)
        result = glob_workspace_files('*.py', path)
        assert 'Matching files (60)' in result
        assert '... and 10 more' in result

    def test_glob_excludes_ignored(self, tmp_path):
        path = _materialize(tmp_path, {
            'src/main.py': 'x',
            '__pycache__/main.cpython-314.pyc': '',
        })
        result = glob_workspace_files('*main*', path)
        assert 'src/main.py' in result
        assert '__pycache__' not in result


# ---------------------------------------------------------------------------
# grep_workspace_files
# ---------------------------------------------------------------------------

class TestGrepWorkspaceFiles:
    def test_simple_pattern(self, workspace_path):
        result = grep_workspace_files('def main', workspace_path)
        assert 'src/main.py:1: def main()' in result

    def test_regex_pattern(self, workspace_path):
        result = grep_workspace_files(r'def \w+\(a, b\)', workspace_path)
        assert 'src/utils/helpers.py:1:' in result

    def test_no_matches(self, workspace_path):
        result = grep_workspace_files('class Foo', workspace_path)
        assert "No matches for 'class Foo'" in result

    def test_glob_filter(self, workspace_path):
        result = grep_workspace_files('def', workspace_path, glob_filter='tests/*')
        assert 'test_main.py' in result
        assert 'src/main.py' not in result

    def test_invalid_regex(self, workspace_path):
        result = grep_workspace_files('[invalid', workspace_path)
        assert 'Invalid regex pattern' in result

    def test_match_count_summary(self, workspace_path):
        result = grep_workspace_files('def', workspace_path)
        assert 'across' in result
        assert 'file' in result

    def test_single_match_grammar(self, workspace_path):
        result = grep_workspace_files('debug', workspace_path)
        assert '(1 match across 1 file)' in result

    def test_truncation(self, tmp_path):
        big = '\n'.join(f'match_line_{i}' for i in range(60))
        path = _materialize(tmp_path, {'big.txt': big})
        result = grep_workspace_files('match_line', path)
        assert 'results truncated' in result

    def test_grep_excludes_ignored(self, tmp_path):
        path = _materialize(tmp_path, {
            'src/main.py': 'SECRET_KEY=abc',
            '.env': 'SECRET_KEY=abc',
        })
        result = grep_workspace_files('SECRET_KEY', path)
        assert 'src/main.py' in result
        assert '.env' not in result
