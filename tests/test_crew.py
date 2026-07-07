import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest
from devteam import settings
from devteam.crew.agents_factory import AgentsFactory
from devteam.crew.crew_factory import CrewFactory
from devteam.crew.event_emitter import EventEmitter
from devteam.crew.execution import Execution
from devteam.crew.history import History
from devteam.crew.final_result import FinalResult


# =====================================================================
# AgentsFactory.fanout_transform
# =====================================================================

class TestFanoutTransform:
    def _base_config(self):
        return {
            'manager': 'ProjectManager',
            'fanout': {'judge': {'class': 'CodeJudge', 'config': 'code-judge.md'}},
            'agents': {
                'developer': {'class': 'SeniorDeveloper', 'config': 'dev.md',
                              'capabilities': ['code-generation'], 'temperature': 0.1},
                'reviewer': {'class': 'CodeReviewer', 'config': 'rev.md'},
            },
        }

    def test_replaces_developer_with_a_b_judge(self):
        out = AgentsFactory.fanout_transform(self._base_config())
        agents = out['agents']
        assert 'developer_a' in agents
        assert 'developer_b' in agents
        assert 'judge' in agents
        assert 'developer' not in agents
        assert 'reviewer' in agents  # other agents preserved

    def test_developer_b_gets_reasoning_capability(self):
        out = AgentsFactory.fanout_transform(self._base_config())
        caps_b = out['agents']['developer_b']['capabilities']
        assert caps_b['reasoning'] >= 1.0
        assert caps_b['code-generation'] == 1.0

    def test_developer_b_temperature_doubled(self):
        out = AgentsFactory.fanout_transform(self._base_config())
        assert out['agents']['developer_b']['temperature'] == pytest.approx(0.2)

    def test_no_developer_returns_unchanged(self):
        config = {'agents': {'reviewer': {'class': 'CodeReviewer', 'config': 'r.md'}}}
        assert AgentsFactory.fanout_transform(config) is config

    def test_already_fanned_out_returns_unchanged(self):
        config = {'agents': {'developer': {}, 'developer_a': {}}}
        assert AgentsFactory.fanout_transform(config) is config

    def test_dict_capabilities_preserved(self):
        config = self._base_config()
        config['agents']['developer']['capabilities'] = {'code-generation': 0.8}
        out = AgentsFactory.fanout_transform(config)
        caps_b = out['agents']['developer_b']['capabilities']
        assert caps_b['code-generation'] == 0.8
        assert caps_b['reasoning'] == 1.0

    def test_explicit_developer_b_class_override_skips_caps_injection(self):
        config = self._base_config()
        config['fanout']['developer_b'] = {'class': 'Migrator', 'config': 'm.md'}
        out = AgentsFactory.fanout_transform(config)
        assert out['agents']['developer_b']['class'] == 'Migrator'


# =====================================================================
# AgentsFactory.create_agents_from_config
# =====================================================================

class TestCreateAgents:
    def test_create_agents_from_config_instantiates(self):
        factory = AgentsFactory(llm_factory=MagicMock(), rate_limiter=None)
        config = {'agents': {
            'pm': {'class': 'ProductManager', 'config': 'product-manager.md'},
        }}
        agents = factory.create_agents_from_config(config)
        assert 'pm' in agents
        assert agents['pm'].__class__.__name__ == 'ProductManager'

    def test_unknown_agent_class_raises(self):
        factory = AgentsFactory(llm_factory=MagicMock())
        config = {'agents': {'x': {'class': 'NoSuchAgent', 'config': 'a.md'}}}
        with pytest.raises(ValueError, match="not a valid class"):
            factory.create_agents_from_config(config)

    def test_no_docker_uses_alternate_config(self, monkeypatch):
        monkeypatch.setattr(settings, 'no_docker', True)
        factory = AgentsFactory(llm_factory=MagicMock())
        config = {'agents': {'qa': {
            'class': 'QAEngineer', 'config': 'qa-engineer-sandbox.md',
            'config-no-docker': 'qa-engineer.md', 'sandbox': 'DockerSandbox'}}}
        agents = factory.create_agents_from_config(config)
        # Sandbox skipped, so the agent has no sandbox attached.
        assert agents['qa'].sandbox is None

    def test_unknown_sandbox_class_raises(self, monkeypatch):
        monkeypatch.setattr(settings, 'no_docker', False)
        factory = AgentsFactory(llm_factory=MagicMock())
        config = {'agents': {'qa': {
            'class': 'QAEngineer', 'config': 'qa-engineer.md', 'sandbox': 'NoSuchSandbox'}}}
        with pytest.raises(ValueError, match="not a valid class in devteam.tools"):
            factory.create_agents_from_config(config)

    def test_load_crew_config_reads_yaml(self):
        factory = AgentsFactory(llm_factory=MagicMock())
        config = factory.load_crew_config('basic.yaml')
        assert config['manager'] == 'ProjectManager'

    def test_create_agents_reads_then_builds(self, monkeypatch):
        monkeypatch.setattr(settings, 'no_docker', True)
        factory = AgentsFactory(llm_factory=MagicMock())
        agents = factory.create_agents('basic.yaml')
        assert 'pm' in agents and 'reporter' in agents


# =====================================================================
# CrewFactory
# =====================================================================

class TestCrewFactory:
    @pytest.fixture(autouse=True)
    def _no_docker(self, monkeypatch):
        monkeypatch.setattr(settings, 'no_docker', True)

    def test_resolve_manager_default(self):
        cf = CrewFactory(llm_factory=MagicMock())
        manager = cf._resolve_manager({})
        assert manager.__name__ == 'ProjectManager'

    def test_resolve_manager_named(self):
        cf = CrewFactory(llm_factory=MagicMock())
        manager = cf._resolve_manager({'manager': 'MigrationManager'})
        assert manager.__name__ == 'MigrationManager'

    def test_resolve_manager_override(self):
        cf = CrewFactory(llm_factory=MagicMock())
        sentinel = object()
        assert cf._resolve_manager({}, sentinel) is sentinel

    def test_resolve_manager_invalid_raises(self):
        cf = CrewFactory(llm_factory=MagicMock())
        with pytest.raises(ValueError, match="not a valid class"):
            cf._resolve_manager({'manager': 'Nope'})

    def test_default_llm_factory_is_ollama(self):
        cf = CrewFactory()
        assert cf.llm_factory.provider == 'ollama'

    def test_create_builds_virtual_crew(self, tmp_path):
        cf = CrewFactory(llm_factory=MagicMock())
        crew = cf.create(tmp_path, config_name='basic.yaml')
        assert crew.app is not None
        assert crew.manager.__class__.__name__ == 'ProjectManager'

    def test_create_with_rpm_builds_rate_limiter(self, tmp_path):
        cf = CrewFactory(llm_factory=MagicMock())
        crew = cf.create(tmp_path, rpm=10, config_name='basic.yaml')
        assert cf.agents_factory.rate_limiter is not None
        assert cf.agents_factory.rate_limiter.rpm_limit == 10

    def test_create_without_rpm_still_carries_registry_budgets(self, tmp_path):
        # --rpm unset (0): the limiter is built anyway so the registry's
        # per-provider defaults (e.g. groq's free-tier rpm) still throttle.
        factory = MagicMock()
        factory.provider_rpm_defaults = {'groq': 30}
        cf = CrewFactory(llm_factory=factory)
        cf.create(tmp_path, config_name='basic.yaml')
        limiter = cf.agents_factory.rate_limiter
        assert limiter is not None
        assert limiter.rpm_for('groq') == 30
        assert limiter.rpm_for('ollama') == 0

    def test_create_fanout(self, tmp_path):
        cf = CrewFactory(llm_factory=MagicMock())
        crew = cf.create(tmp_path, config_name='basic.yaml', fanout=True)
        assert 'developer_a' in crew.manager.agents


# =====================================================================
# EventEmitter
# =====================================================================

class _Emitter(EventEmitter):
    def __init__(self, extensions):
        self.all_extensions = extensions
        import logging
        self.logger = logging.getLogger('test')


class TestEventEmitter:
    def test_emit_merges_dict_results(self):
        ext = MagicMock()
        ext.critical = False
        ext.on_step = AsyncMock(return_value={'a': 1})
        ext2 = MagicMock()
        ext2.critical = False
        ext2.on_step = AsyncMock(return_value={'b': 2})
        emitter = _Emitter([ext, ext2])
        result = asyncio.run(emitter.emit_event('step', 't1', foo='bar'))
        assert result == {'a': 1, 'b': 2}

    def test_emit_returns_none_when_no_results(self):
        ext = MagicMock()
        ext.critical = False
        ext.on_step = AsyncMock(return_value=None)
        emitter = _Emitter([ext])
        assert asyncio.run(emitter.emit_event('step', 't1')) is None

    def test_emit_skips_extension_without_method(self):
        ext = object()  # no on_step
        emitter = _Emitter([ext])
        assert asyncio.run(emitter.emit_event('step', 't1')) is None

    def test_emit_abort_short_circuits(self):
        ext1 = MagicMock()
        ext1.critical = False
        ext1.on_step = AsyncMock(return_value={'abort_requested': True})
        ext2 = MagicMock()
        ext2.critical = False
        ext2.on_step = AsyncMock(return_value={'should_not': 'merge'})
        emitter = _Emitter([ext1, ext2])
        result = asyncio.run(emitter.emit_event('step', 't1'))
        assert result == {'abort_requested': True}
        ext2.on_step.assert_not_called()

    def test_emit_non_critical_error_swallowed(self):
        ext = MagicMock()
        ext.critical = False
        ext.on_step = AsyncMock(side_effect=RuntimeError("boom"))
        emitter = _Emitter([ext])
        assert asyncio.run(emitter.emit_event('step', 't1')) is None

    def test_emit_critical_error_raises(self):
        ext = MagicMock()
        ext.critical = True
        ext.on_step = AsyncMock(side_effect=RuntimeError("boom"))
        emitter = _Emitter([ext])
        with pytest.raises(RuntimeError):
            asyncio.run(emitter.emit_event('step', 't1'))


# =====================================================================
# History
# =====================================================================

class _HistoryCrew(History):
    def __init__(self, snapshots):
        self.app = MagicMock()

        async def _gen(config):
            for s in snapshots:
                yield s
        self.app.aget_state_history = _gen


def _snapshot(c_id, created_at, next_node):
    snap = MagicMock()
    snap.config = {'configurable': {'checkpoint_id': c_id}}
    snap.created_at = created_at
    snap.next = (next_node,) if next_node else ()
    return snap


class TestHistory:
    def test_get_history_dedups_and_sorts(self):
        crew = _HistoryCrew([
            _snapshot('c1', '2026-01-01T00:00:00', 'pm'),
            _snapshot('c1', '2026-01-01T00:00:00', 'pm'),  # duplicate
            _snapshot('c2', '2026-01-02T00:00:00', None),
        ])
        history = asyncio.run(crew.get_history('t1'))
        assert len(history) == 2
        # Sorted descending by time -> c2 first.
        assert history[0]['c_id'] == 'c2'

    def test_get_history_uses_end_for_no_next(self):
        from langgraph.graph import END
        crew = _HistoryCrew([_snapshot('c1', '2026-01-01T00:00:00', None)])
        history = asyncio.run(crew.get_history('t1'))
        assert history[0]['node'] == END


# =====================================================================
# FinalResult
# =====================================================================

class TestFinalResult:
    def test_success_when_clean(self):
        r = FinalResult(thread_id='t')
        assert r.success is True
        assert r.has_bugs is False

    def test_failure_when_bugs(self):
        r = FinalResult(thread_id='t', integration_bugs=['bug'])
        assert r.success is False
        assert r.has_bugs is True

    def test_aborted_is_not_success(self):
        r = FinalResult(thread_id='t', abort_requested=True)
        assert r.success is False

    def test_extra_fields_ignored(self):
        r = FinalResult(thread_id='t', unknown_field='x', specs='ignored too')
        assert r.thread_id == 't'


# =====================================================================
# Execution.execute / _inject_feedback
# =====================================================================

class _ExecCrew(Execution):
    def __init__(self):
        import logging
        self.logger = logging.getLogger('exec-test')
        self.all_extensions = []
        self.app = MagicMock()


def _make_state_snapshot(values, next_nodes=()):
    snap = MagicMock()
    snap.values = dict(values)
    snap.next = next_nodes
    snap.config = {'configurable': {'thread_id': 't1'}}
    return snap


class TestExecution:
    def test_inject_feedback_reviewer(self):
        crew = _ExecCrew()
        crew.app.aget_state = AsyncMock(return_value=_make_state_snapshot({}))
        crew.app.aupdate_state = AsyncMock()
        update = asyncio.run(crew._inject_feedback({'configurable': {}}, 'fix it', 'reviewer'))
        assert 'CRITICAL HUMAN FEEDBACK' in update['review_feedback']
        assert update['current_phase'] == 'development'

    def test_inject_feedback_qa(self):
        crew = _ExecCrew()
        crew.app.aget_state = AsyncMock(return_value=_make_state_snapshot({}))
        crew.app.aupdate_state = AsyncMock()
        update = asyncio.run(crew._inject_feedback({'configurable': {}}, 'fix', 'qa'))
        assert 'test_results' in update

    def test_inject_feedback_pm(self):
        crew = _ExecCrew()
        crew.app.aget_state = AsyncMock(return_value=_make_state_snapshot({}))
        crew.app.aupdate_state = AsyncMock()
        update = asyncio.run(crew._inject_feedback({'configurable': {}}, 'fix', 'pm'))
        assert update['current_phase'] == 'planning'

    def test_inject_feedback_other(self):
        crew = _ExecCrew()
        crew.app.aget_state = AsyncMock(return_value=_make_state_snapshot({}))
        crew.app.aupdate_state = AsyncMock()
        update = asyncio.run(crew._inject_feedback({'configurable': {}}, 'note', 'human'))
        assert 'communication_log' in update

    def test_execute_simple_completion(self, tmp_path):
        crew = _ExecCrew()
        final_values = {'workspace_path': str(tmp_path), 'current_phase': 'development'}

        async def _astream(initial_state, config, stream_mode):
            yield {'pm': {'specs': 'x'}}
        crew.app.astream = _astream
        # After streaming, no next node -> loop ends.
        crew.app.aget_state = AsyncMock(return_value=_make_state_snapshot(final_values, next_nodes=()))

        result = asyncio.run(crew.execute('t1', requirements='build'))
        assert isinstance(result, FinalResult)
        assert result.thread_id == 't1'

    def test_execute_aborts_when_requested(self, tmp_path):
        crew = _ExecCrew()

        async def _astream(initial_state, config, stream_mode):
            yield {'manager': {'abort_requested': True}}
        crew.app.astream = _astream
        crew.app.aget_state = AsyncMock(return_value=_make_state_snapshot(
            {'abort_requested': True, 'workspace_path': str(tmp_path)}, next_nodes=()))

        result = asyncio.run(crew.execute('t1', requirements='build'))
        assert result.abort_requested is True
