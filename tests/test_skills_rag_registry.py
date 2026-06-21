import asyncio
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest
from devteam import settings
from devteam.skills import skills
from devteam.tools import rag
from devteam.tools import registry
from devteam.state import ProjectState


# =====================================================================
# skills
# =====================================================================

@pytest.fixture
def skills_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'skills_dir', tmp_path)
    skills.load_skills_catalog.cache_clear()
    skills.load_skill.cache_clear()
    yield tmp_path
    skills.load_skills_catalog.cache_clear()
    skills.load_skill.cache_clear()


def _write_skill(base: Path, name: str, description: str, body: str = "How to do it."):
    folder = base / name
    folder.mkdir()
    (folder / 'SKILL.md').write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n{body}",
        encoding='utf-8',
    )


class TestSkillsCatalog:
    def test_load_catalog_reads_metadata(self, skills_dir):
        _write_skill(skills_dir, 'flask-api', 'Build Flask APIs')
        catalog = skills.load_skills_catalog()
        assert {'name': 'flask-api', 'description': 'Build Flask APIs'} in catalog

    def test_load_catalog_missing_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, 'skills_dir', tmp_path / 'nope')
        skills.load_skills_catalog.cache_clear()
        assert skills.load_skills_catalog() == []

    def test_load_catalog_skips_files_without_frontmatter(self, skills_dir):
        folder = skills_dir / 'bad'
        folder.mkdir()
        (folder / 'SKILL.md').write_text("no frontmatter here", encoding='utf-8')
        assert skills.load_skills_catalog() == []

    def test_load_catalog_handles_parse_error(self, skills_dir):
        folder = skills_dir / 'broken'
        folder.mkdir()
        (folder / 'SKILL.md').write_text("---\n: : bad yaml : :\n---\nbody", encoding='utf-8')
        # Should not raise.
        skills.load_skills_catalog()


class TestLoadSkill:
    def test_load_skill_returns_body(self, skills_dir):
        _write_skill(skills_dir, 'testing', 'Testing skill', body="Write good tests.")
        content = skills.load_skill('testing')
        assert content == "Write good tests."

    def test_load_skill_missing(self, skills_dir):
        result = skills.load_skill('ghost')
        assert "does not exist" in result

    def test_load_skill_strips_path_traversal(self, skills_dir):
        _write_skill(skills_dir, 'safe', 'desc', body="safe body")
        # Path() name strips directory components.
        result = skills.load_skill('../../safe')
        assert result == "safe body"

    def test_load_skill_without_frontmatter_returns_full(self, skills_dir):
        folder = skills_dir / 'plain'
        folder.mkdir()
        (folder / 'SKILL.md').write_text("Just content, no frontmatter.", encoding='utf-8')
        assert skills.load_skill('plain') == "Just content, no frontmatter."


# =====================================================================
# rag
# =====================================================================

@pytest.fixture(autouse=True)
def _clear_rag_caches():
    rag._load_sources.cache_clear()
    rag._resolve_source.cache_clear()
    rag.rag_sources_catalog.cache_clear()
    yield
    rag._load_sources.cache_clear()
    rag._resolve_source.cache_clear()
    rag.rag_sources_catalog.cache_clear()


class TestRagSources:
    def test_load_sources_from_config_dir(self):
        # Falls back to the bundled config/tools/rag.yaml.
        sources = rag._load_sources()
        assert 'default' in sources

    def test_load_sources_missing_returns_empty(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(settings, 'tools_config_dir', tmp_path / 'missing')
        rag._load_sources.cache_clear()
        assert rag._load_sources() == {}

    def test_resolve_source_named(self, monkeypatch):
        monkeypatch.setattr(rag, '_load_sources', lambda: {
            'docs': {'mcp_url': 'http://docs', 'mcp_tool': 'find'},
        })
        rag._resolve_source.cache_clear()
        url, tool, extra = rag._resolve_source('docs')
        assert url == 'http://docs'
        assert tool == 'find'
        assert extra == {}

    def test_resolve_source_default_with_filter(self, monkeypatch):
        monkeypatch.setattr(rag, '_load_sources', lambda: {})
        rag._resolve_source.cache_clear()
        url, tool, extra = rag._resolve_source('some-source')
        assert extra == {'filter': {'source': 'some-source'}}

    def test_sources_catalog_formats(self, monkeypatch):
        monkeypatch.setattr(rag, '_load_sources', lambda: {
            'docs': {'description': 'Internal docs'},
            'api': {},
        })
        rag.rag_sources_catalog.cache_clear()
        catalog = rag.rag_sources_catalog()
        assert '`docs`: Internal docs' in catalog
        assert '`api`' in catalog

    def test_sources_catalog_empty(self, monkeypatch):
        monkeypatch.setattr(rag, '_load_sources', lambda: {})
        rag.rag_sources_catalog.cache_clear()
        assert rag.rag_sources_catalog() == ''

    def test_init_retrieve_context_tool_patches_description(self, monkeypatch):
        monkeypatch.setattr(rag, 'rag_sources_catalog', lambda: '- `docs`')
        rag.init_retrieve_context_tool()
        from devteam.tools.schemas import RetrieveContext
        assert 'docs' in RetrieveContext.model_fields['source'].description

    def test_init_retrieve_context_tool_noop_when_empty(self, monkeypatch):
        monkeypatch.setattr(rag, 'rag_sources_catalog', lambda: '')
        # Should not raise.
        rag.init_retrieve_context_tool()


class TestRetrieveContext:
    def test_retrieve_context_handles_connection_error(self, monkeypatch):
        monkeypatch.setattr(rag, '_resolve_source', lambda s: ('http://x', 'find', {}))

        # Make the mcp client raise on use.
        import mcp
        def boom(*a, **k):
            raise ConnectionError("no server")
        monkeypatch.setattr('mcp.client.streamable_http.streamable_http_client', boom, raising=False)
        result = asyncio.run(rag.retrieve_context('query'))
        assert 'Knowledge base unavailable' in result


# =====================================================================
# tool registry
# =====================================================================

class TestToolRegistry:
    def test_register_and_get(self):
        reg = registry.ToolRegistry()
        from devteam.tools.schemas import ReadFile
        reg.register('ReadFile', ReadFile)
        assert 'ReadFile' in reg
        assert reg.get_schema('ReadFile') is ReadFile
        assert reg.get('ReadFile').schema is ReadFile

    def test_get_missing_returns_none(self):
        reg = registry.ToolRegistry()
        assert reg.get('x') is None
        assert reg.get_schema('x') is None
        assert reg.get_handler('x') is None

    def test_tool_entry_is_enabled(self):
        from devteam.tools.schemas import ReadFile
        entry = registry.ToolEntry(ReadFile, enabled_when=lambda s: s.rag_enabled)
        assert entry.is_enabled(settings) == settings.rag_enabled
        always = registry.ToolEntry(ReadFile)
        assert always.is_enabled(settings) is True

    def test_builtins_registered(self):
        assert 'ReadFile' in registry.tool_registry
        assert 'LoadSkill' in registry.tool_registry
        assert 'GrepFiles' in registry.tool_registry

    def test_handle_load_skill(self, monkeypatch):
        monkeypatch.setattr(registry.skills, 'load_skill', lambda n: f"BODY:{n}")
        out = asyncio.run(registry._handle_load_skill(
            {'skill_names': ['a', 'b']}, ProjectState(), logging.getLogger('t')))
        assert 'BODY:a' in out and 'BODY:b' in out

    def test_handle_read_file(self, workspace_dir):
        out = asyncio.run(registry._handle_read_file(
            {'path': 'src/main.py'}, ProjectState(workspace_path=workspace_dir),
            logging.getLogger('t')))
        assert 'FILE: src/main.py' in out

    def test_handle_list_files(self, workspace_dir):
        out = asyncio.run(registry._handle_list_files(
            {}, ProjectState(workspace_path=workspace_dir), logging.getLogger('t')))
        assert 'src/main.py' in out

    def test_handle_glob_files(self, workspace_dir):
        out = asyncio.run(registry._handle_glob_files(
            {'pattern': '*.py'}, ProjectState(workspace_path=workspace_dir),
            logging.getLogger('t')))
        assert 'main.py' in out

    def test_handle_grep_files(self, workspace_dir):
        out = asyncio.run(registry._handle_grep_files(
            {'pattern': 'hello', 'glob': '*.py'},
            ProjectState(workspace_path=workspace_dir), logging.getLogger('t')))
        assert 'main.py' in out

    def test_handle_retrieve_context(self, monkeypatch):
        async def fake_retrieve(query, source=None):
            return f"chunks for {query}"
        monkeypatch.setattr(registry.rag, 'retrieve_context', fake_retrieve)
        out = asyncio.run(registry._handle_retrieve_context(
            {'query': 'auth', 'source': 'docs'}, ProjectState(), logging.getLogger('t')))
        assert out == 'chunks for auth'
