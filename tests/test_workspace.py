import pytest
from devteam.utils.workspace import (
    _is_excluded,
    read_workspace_file,
    list_workspace_files,
    glob_workspace_files,
    grep_workspace_files,
)

WORKSPACE_FILES = {
    'src/main.py': 'def main():\n    print("hello")\n',
    'src/utils/helpers.py': 'def add(a, b):\n    return a + b\n',
    'tests/test_main.py': 'def test_main():\n    assert True\n',
    'README.md': '# My Project\nA simple project.\n',
    'config/settings.yaml': 'debug: true\n',
}

NO_WORKSPACE_PATH = ''


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
# read_workspace_file
# ---------------------------------------------------------------------------

class TestReadWorkspaceFile:
    def test_reads_from_memory(self):
        result = read_workspace_file('src/main.py', WORKSPACE_FILES, NO_WORKSPACE_PATH)
        assert '--- FILE: src/main.py ---' in result
        assert 'def main()' in result

    def test_reads_from_disk(self, tmp_path):
        disk_file = tmp_path / 'on_disk.py'
        disk_file.write_text('x = 1', encoding='utf-8')
        result = read_workspace_file('on_disk.py', {}, str(tmp_path))
        assert '--- FILE: on_disk.py ---' in result
        assert 'x = 1' in result

    def test_memory_takes_precedence_over_disk(self, tmp_path):
        disk_file = tmp_path / 'src' / 'main.py'
        disk_file.parent.mkdir(parents=True)
        disk_file.write_text('DISK VERSION', encoding='utf-8')
        result = read_workspace_file('src/main.py', WORKSPACE_FILES, str(tmp_path))
        assert 'def main()' in result
        assert 'DISK VERSION' not in result

    def test_not_found_lists_available(self):
        result = read_workspace_file('nope.py', WORKSPACE_FILES, NO_WORKSPACE_PATH)
        assert "File not found: 'nope.py'" in result
        assert 'src/main.py' in result

    def test_path_traversal_blocked(self, tmp_path):
        secret = tmp_path.parent / 'secret.txt'
        secret.write_text('secret', encoding='utf-8')
        result = read_workspace_file('../secret.txt', {}, str(tmp_path))
        assert 'File not found' in result

    def test_excluded_file_blocked(self):
        files = {'.env': 'SECRET_KEY=abc123'}
        result = read_workspace_file('.env', files, NO_WORKSPACE_PATH)
        assert 'Access denied' in result
        assert 'SECRET_KEY' not in result


# ---------------------------------------------------------------------------
# list_workspace_files
# ---------------------------------------------------------------------------

class TestListWorkspaceFiles:
    def test_lists_memory_files(self):
        result = list_workspace_files(WORKSPACE_FILES, NO_WORKSPACE_PATH)
        assert 'Workspace files (5)' in result
        assert '- src/main.py' in result
        assert '- README.md' in result

    def test_includes_disk_files(self, tmp_path):
        (tmp_path / 'extra.txt').write_text('hi', encoding='utf-8')
        result = list_workspace_files({'a.py': 'x'}, str(tmp_path))
        assert '- a.py' in result
        assert '- extra.txt' in result

    def test_empty_workspace(self):
        result = list_workspace_files({}, NO_WORKSPACE_PATH)
        assert result == 'No files in workspace.'

    def test_excludes_ignored_files(self):
        files = {'src/main.py': 'x', '.env': 'SECRET', '__pycache__/mod.pyc': ''}
        result = list_workspace_files(files, NO_WORKSPACE_PATH)
        assert 'src/main.py' in result
        assert '.env' not in result
        assert '__pycache__' not in result


# ---------------------------------------------------------------------------
# glob_workspace_files
# ---------------------------------------------------------------------------

class TestGlobWorkspaceFiles:
    def test_glob_py_files(self):
        result = glob_workspace_files('*.py', WORKSPACE_FILES, NO_WORKSPACE_PATH)
        assert 'src/main.py' in result
        assert 'README.md' not in result

    def test_glob_src_py(self):
        result = glob_workspace_files('src/*.py', WORKSPACE_FILES, NO_WORKSPACE_PATH)
        assert '- src/main.py' in result
        assert 'README.md' not in result
        assert 'test_main.py' not in result

    def test_glob_md_files(self):
        result = glob_workspace_files('*.md', WORKSPACE_FILES, NO_WORKSPACE_PATH)
        assert '- README.md' in result
        assert 'main.py' not in result

    def test_glob_no_matches(self):
        result = glob_workspace_files('*.rs', WORKSPACE_FILES, NO_WORKSPACE_PATH)
        assert "No files matching '*.rs'" in result

    def test_glob_with_disk_files(self, tmp_path):
        (tmp_path / 'data.json').write_text('{}', encoding='utf-8')
        result = glob_workspace_files('*.json', {}, str(tmp_path))
        assert '- data.json' in result

    def test_glob_truncation(self):
        many_files = {f'file_{i:03d}.py': '' for i in range(60)}
        result = glob_workspace_files('*.py', many_files, NO_WORKSPACE_PATH)
        assert 'Matching files (60)' in result
        assert '... and 10 more' in result

    def test_glob_excludes_ignored(self):
        files = {'src/main.py': 'x', '__pycache__/main.cpython-314.pyc': ''}
        result = glob_workspace_files('*main*', files, NO_WORKSPACE_PATH)
        assert 'src/main.py' in result
        assert '__pycache__' not in result


# ---------------------------------------------------------------------------
# grep_workspace_files
# ---------------------------------------------------------------------------

class TestGrepWorkspaceFiles:
    def test_simple_pattern(self):
        result = grep_workspace_files('def main', WORKSPACE_FILES, NO_WORKSPACE_PATH)
        assert 'src/main.py:1: def main()' in result

    def test_regex_pattern(self):
        result = grep_workspace_files(r'def \w+\(a, b\)', WORKSPACE_FILES, NO_WORKSPACE_PATH)
        assert 'src/utils/helpers.py:1:' in result

    def test_no_matches(self):
        result = grep_workspace_files('class Foo', WORKSPACE_FILES, NO_WORKSPACE_PATH)
        assert "No matches for 'class Foo'" in result

    def test_glob_filter(self):
        result = grep_workspace_files('def', WORKSPACE_FILES, NO_WORKSPACE_PATH, glob_filter='tests/*')
        assert 'test_main.py' in result
        assert 'src/main.py' not in result

    def test_invalid_regex(self):
        result = grep_workspace_files('[invalid', WORKSPACE_FILES, NO_WORKSPACE_PATH)
        assert 'Invalid regex pattern' in result

    def test_match_count_summary(self):
        result = grep_workspace_files('def', WORKSPACE_FILES, NO_WORKSPACE_PATH)
        assert 'across' in result
        assert 'file' in result

    def test_single_match_grammar(self):
        result = grep_workspace_files('debug', WORKSPACE_FILES, NO_WORKSPACE_PATH)
        assert '(1 match across 1 file)' in result

    def test_truncation(self):
        big_file = '\n'.join(f'match_line_{i}' for i in range(60))
        files = {'big.txt': big_file}
        result = grep_workspace_files('match_line', files, NO_WORKSPACE_PATH)
        assert 'results truncated' in result

    def test_reads_from_disk(self, tmp_path):
        disk_file = tmp_path / 'disk.py'
        disk_file.write_text('secret_function = True', encoding='utf-8')
        result = grep_workspace_files('secret_function', {}, str(tmp_path))
        assert 'disk.py:1:' in result

    def test_grep_excludes_ignored(self):
        files = {'src/main.py': 'SECRET_KEY=abc', '.env': 'SECRET_KEY=abc'}
        result = grep_workspace_files('SECRET_KEY', files, NO_WORKSPACE_PATH)
        assert 'src/main.py' in result
        assert '.env' not in result
