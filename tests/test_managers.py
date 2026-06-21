import pytest
from langgraph.graph import END
from langchain_core.messages import HumanMessage
from devteam import settings
from devteam.managers.project_manager import ProjectManager
from devteam.managers.migration_manager import MigrationManager
from devteam.state import ProjectState, TaskContext


@pytest.fixture(autouse=True)
def _reset_approval_flags():
    saved = (settings.ask_approval, settings.ask_all)
    settings.ask_approval = False
    settings.ask_all = False
    yield
    settings.ask_approval, settings.ask_all = saved


def make_pm(agents=None):
    return ProjectManager(agents=agents or {})


# =====================================================================
# ExecutionManager._find_next_task / _officer_node
# =====================================================================

class TestOfficer:
    def test_find_next_task_respects_dependencies(self):
        mgr = make_pm()
        state = ProjectState(
            pending_tasks=[
                {'task_name': 'B', 'dependencies': ['A']},
                {'task_name': 'A', 'dependencies': []},
            ],
            completed_tasks=[],
        )
        task = mgr._find_next_task(state)
        assert task['task_name'] == 'A'

    def test_find_next_task_skips_completed(self):
        mgr = make_pm()
        state = ProjectState(
            pending_tasks=[{'task_name': 'A', 'dependencies': []}],
            completed_tasks=['A'],
        )
        assert mgr._find_next_task(state) is None

    def test_officer_routes_to_integration_when_all_done(self):
        mgr = make_pm()
        state = ProjectState(
            current_phase='development',
            pending_tasks=[{'task_name': 'A'}],
            completed_tasks=['A'],
        )
        result = mgr._officer_node(state)
        assert result['current_phase'] == 'integration'
        assert isinstance(result['task_context'], TaskContext)

    def test_officer_detects_dependency_deadlock(self):
        mgr = make_pm()
        # B depends on missing C, A depends on B -> nothing ready, none complete
        state = ProjectState(
            current_phase='development',
            pending_tasks=[{'task_name': 'B', 'dependencies': ['C']}],
            completed_tasks=[],
        )
        result = mgr._officer_node(state)
        assert result['current_phase'] == 'integration'

    def test_officer_starts_ready_task(self):
        mgr = make_pm(agents={'developer': object()})
        state = ProjectState(
            current_phase='development',
            pending_tasks=[{'task_name': 'A', 'complexity': 'low'}],
            completed_tasks=[],
        )
        result = mgr._officer_node(state)
        tc = result['task_context']
        assert tc.current_task_name == 'A'
        assert tc.current_agent == 'developer'
        assert tc.current_task_index == 1
        assert tc.current_task_complexity == 'low'

    def test_developer_node_prefers_fanout(self):
        mgr = make_pm(agents={'developer_a': object(), 'developer_b': object()})
        assert mgr._developer_node == 'developer_a'

    def test_developer_node_single(self):
        mgr = make_pm(agents={'developer': object()})
        assert mgr._developer_node == 'developer'


# =====================================================================
# ExecutionManager._execution_node state machine
# =====================================================================

class TestExecutionNode:
    def _ctx(self, **kw):
        return TaskContext(**kw)

    def test_human_feedback_short_circuits(self):
        mgr = make_pm()
        state = ProjectState(task_context=self._ctx(current_agent='developer', human_feedback='please fix'))
        result = mgr._execution_node(state)
        assert result['task_context'].human_feedback == ''
        assert isinstance(result['messages'][0], HumanMessage)

    def test_developer_a_goes_to_developer_b_initially(self):
        mgr = make_pm()
        state = ProjectState(task_context=self._ctx(current_agent='developer_a'))
        result = mgr._execution_node(state)
        assert result['task_context'].current_agent == 'developer_b'

    def test_developer_a_goes_to_reviewer_after_winner(self):
        mgr = make_pm()
        state = ProjectState(task_context=self._ctx(current_agent='developer_a', winner_developer='developer_a'))
        result = mgr._execution_node(state)
        assert result['task_context'].current_agent == 'reviewer'

    def test_developer_b_goes_to_judge(self):
        mgr = make_pm()
        state = ProjectState(task_context=self._ctx(current_agent='developer_b'))
        result = mgr._execution_node(state)
        assert result['task_context'].current_agent == 'judge'

    def test_judge_goes_to_reviewer(self):
        mgr = make_pm()
        state = ProjectState(task_context=self._ctx(current_agent='judge'))
        result = mgr._execution_node(state)
        assert result['task_context'].current_agent == 'reviewer'

    def test_developer_goes_to_reviewer(self):
        mgr = make_pm()
        state = ProjectState(task_context=self._ctx(current_agent='developer'))
        result = mgr._execution_node(state)
        assert result['task_context'].current_agent == 'reviewer'

    def test_reviewer_rejection_triggers_revision(self):
        mgr = make_pm()
        mgr.max_revision_count = 3
        state = ProjectState(task_context=self._ctx(
            current_agent='reviewer', review_feedback='- bug: missing', revision_count=0))
        result = mgr._execution_node(state)
        assert result['task_context'].current_agent == 'developer'
        assert result['task_context'].revision_count == 1
        assert any('Revision' in m for m in result['communication_log'])

    def test_reviewer_rejection_uses_winner_for_revision(self):
        mgr = make_pm()
        mgr.max_revision_count = 3
        state = ProjectState(task_context=self._ctx(
            current_agent='reviewer', review_feedback='- bug', revision_count=0,
            winner_developer='developer_b'))
        result = mgr._execution_node(state)
        assert result['task_context'].current_agent == 'developer_b'

    def test_reviewer_rejection_at_max_revisions_goes_to_qa(self):
        mgr = make_pm()
        mgr.max_revision_count = 2
        state = ProjectState(task_context=self._ctx(
            current_agent='reviewer', review_feedback='- bug', revision_count=2))
        result = mgr._execution_node(state)
        assert result['task_context'].current_agent == 'qa'

    def test_approved_review_goes_to_qa(self):
        mgr = make_pm()
        state = ProjectState(task_context=self._ctx(
            current_agent='reviewer', review_feedback='APPROVED'))
        result = mgr._execution_node(state)
        assert result['task_context'].current_agent == 'qa'

    def test_qa_failure_triggers_revision(self):
        mgr = make_pm()
        mgr.max_revision_count = 3
        state = ProjectState(task_context=self._ctx(
            current_agent='qa', review_feedback='APPROVED',
            test_results='- bug in tests', revision_count=0))
        result = mgr._execution_node(state)
        assert result['task_context'].current_agent == 'developer'
        assert any('QA' in m for m in result['communication_log'])

    def test_qa_pass_completes_task(self):
        mgr = make_pm()
        state = ProjectState(task_context=self._ctx(
            current_agent='qa', current_task_name='A',
            review_feedback='APPROVED', test_results='PASSED'))
        result = mgr._execution_node(state)
        assert result['task_context'].current_agent == 'officer'
        assert result['completed_tasks'] == ['A']

    def test_route_execution_returns_current_agent(self):
        mgr = make_pm()
        state = ProjectState(task_context=self._ctx(current_agent='reviewer'))
        assert mgr._route_execution(state) == 'reviewer'

    def test_route_execution_defaults_to_officer(self):
        mgr = make_pm()
        assert mgr._route_execution(ProjectState()) == 'officer'


# =====================================================================
# BaseManager: manager_node, router, error handling, dummy nodes
# =====================================================================

class TestBaseManager:
    def test_manager_node_dispatches_integration(self):
        mgr = make_pm()
        state = ProjectState(current_phase='integration')
        assert mgr._manager_node(state) == {}

    def test_manager_node_unknown_phase_returns_empty(self):
        mgr = make_pm()
        state = ProjectState(current_phase='complete')
        assert mgr._manager_node(state) == {}

    def test_central_router_abort(self):
        mgr = make_pm()
        state = ProjectState(abort_requested=True)
        assert mgr._central_router(state) == END

    def test_central_router_integration(self):
        mgr = make_pm()
        state = ProjectState(current_phase='integration', final_report='done')
        assert mgr._central_router(state) == END

    def test_central_router_development(self):
        mgr = make_pm()
        state = ProjectState(current_phase='development',
                             task_context=TaskContext(current_agent='qa'))
        assert mgr._central_router(state) == 'qa'

    def test_central_router_complete_phase(self):
        mgr = make_pm()
        assert mgr._central_router(ProjectState(current_phase='complete')) == END

    def test_handle_error_in_planning_aborts(self):
        mgr = make_pm()
        state = ProjectState(current_phase='planning', error=True)
        assert mgr._handle_agent_error(state) == {'abort_requested': True}

    def test_handle_error_in_development_skips_task(self):
        mgr = make_pm()
        state = ProjectState(
            current_phase='development',
            task_context=TaskContext(current_task_name='A', current_task='Build A'),
            error=True,
        )
        result = mgr._handle_agent_error(state)
        assert result['error'] is False
        assert result['completed_tasks'] == ['A']
        assert result['failed_tasks']

    def test_dummy_human_node_clears_question(self):
        mgr = make_pm()
        assert mgr._dummy_human_node(ProjectState()) == {'clarification_question': ''}

    def test_cleanup_messages_only_keeps_messages_with_ids(self):
        mgr = make_pm()
        m1 = HumanMessage(content='a', id='x1')
        m2 = HumanMessage(content='b')  # no id
        result = mgr._cleanup_messages([m1, m2])
        assert len(result) == 1

    def test_build_graph_compiles(self):
        mgr = make_pm(agents={'pm': _FakeAgent(), 'reviewer': _FakeAgent()})
        graph = mgr.build_graph()
        assert graph is not None

    def test_build_graph_with_ask_all_interrupts_after_agents(self):
        settings.ask_all = True
        mgr = make_pm(agents={'pm': _FakeAgent()})
        graph = mgr.build_graph()
        assert graph is not None


class _FakeAgent:
    async def process(self, state):
        return {}


# =====================================================================
# PlanningManager
# =====================================================================

class TestPlanningManager:
    def test_planning_node_auto_approves_tasks(self):
        mgr = make_pm()
        state = ProjectState(pending_tasks=[{'task_name': 'A'}], tasks_approved=False)
        result = mgr._planning_node(state)
        assert result['current_phase'] == 'development'
        assert result['tasks_approved'] is True

    def test_planning_node_waits_for_task_approval(self):
        settings.ask_approval = True
        mgr = make_pm()
        state = ProjectState(pending_tasks=[{'task_name': 'A'}], tasks_approved=False)
        assert mgr._planning_node(state) == {}

    def test_planning_node_auto_approves_specs(self):
        mgr = make_pm()
        state = ProjectState(specs='the spec', specs_approved=False)
        result = mgr._planning_node(state)
        assert result['specs_approved'] is True

    def test_planning_node_waits_for_spec_approval(self):
        settings.ask_all = True
        mgr = make_pm()
        state = ProjectState(specs='the spec', specs_approved=False)
        assert mgr._planning_node(state) == {}

    def test_planning_node_sentinel(self):
        mgr = make_pm()
        assert mgr._planning_node(ProjectState()) == {}

    def test_route_planning_clarification(self):
        mgr = make_pm()
        assert mgr._route_planning(ProjectState(clarification_question='?')) == 'human'

    def test_route_planning_no_specs_goes_to_pm(self):
        mgr = make_pm()
        assert mgr._route_planning(ProjectState()) == 'pm'

    def test_route_planning_specs_not_approved_goes_to_human(self):
        mgr = make_pm()
        assert mgr._route_planning(ProjectState(specs='x', specs_approved=False)) == 'human'

    def test_route_planning_needs_architect(self):
        mgr = make_pm()
        state = ProjectState(specs='x', specs_approved=True)
        assert mgr._route_planning(state) == 'architect'

    def test_route_planning_tasks_not_approved_goes_to_human(self):
        mgr = make_pm()
        state = ProjectState(specs='x', specs_approved=True,
                             pending_tasks=[{'task_name': 'A'}], tasks_approved=False)
        assert mgr._route_planning(state) == 'human'

    def test_route_planning_sentinel_end(self):
        mgr = make_pm()
        state = ProjectState(specs='x', specs_approved=True,
                             pending_tasks=[{'task_name': 'A'}], tasks_approved=True)
        assert mgr._route_planning(state) == END


# =====================================================================
# IntegrationManager
# =====================================================================

class TestIntegrationManager:
    def test_integration_node_noop(self):
        mgr = make_pm()
        assert mgr._integration_node(ProjectState()) == {}

    def test_route_integration_final_report_ends(self):
        mgr = make_pm()
        assert mgr._route_integration(ProjectState(final_report='done')) == END

    def test_route_integration_no_results_goes_to_final_qa(self):
        mgr = make_pm()
        assert mgr._route_integration(ProjectState()) == 'final_qa'

    def test_route_integration_passed_goes_to_reporter(self):
        mgr = make_pm()
        state = ProjectState(task_context=TaskContext(test_results='PASSED'))
        assert mgr._route_integration(state) == 'reporter'

    def test_route_integration_bugs_end(self):
        mgr = make_pm()
        state = ProjectState(task_context=TaskContext(test_results='- integration bug'))
        assert mgr._route_integration(state) == END


# =====================================================================
# MigrationManager
# =====================================================================

class TestMigrationManager:
    def test_planning_node_transitions_to_development(self):
        mgr = MigrationManager(agents={})
        state = ProjectState(specs='analysis', pending_tasks=[{'task_name': 'T'}])
        result = mgr._planning_node(state)
        assert result['current_phase'] == 'development'
        assert result['specs_approved'] is True
        assert result['tasks_approved'] is True

    def test_planning_node_waits_for_approval(self):
        settings.ask_approval = True
        mgr = MigrationManager(agents={})
        state = ProjectState(specs='analysis', pending_tasks=[{'task_name': 'T'}])
        assert mgr._planning_node(state) == {}

    def test_planning_node_incomplete_returns_empty(self):
        mgr = MigrationManager(agents={})
        assert mgr._planning_node(ProjectState()) == {}

    def test_route_planning_clarification(self):
        mgr = MigrationManager(agents={})
        assert mgr._route_planning(ProjectState(clarification_question='?')) == 'human'

    def test_route_planning_no_specs_goes_to_analyzer(self):
        mgr = MigrationManager(agents={})
        assert mgr._route_planning(ProjectState()) == 'analyzer'

    def test_route_planning_tasks_pending_with_approval(self):
        settings.ask_approval = True
        mgr = MigrationManager(agents={})
        state = ProjectState(specs='x', tasks_approved=False)
        assert mgr._route_planning(state) == 'human'

    def test_route_planning_tasks_pending_auto(self):
        mgr = MigrationManager(agents={})
        state = ProjectState(specs='x', tasks_approved=False)
        assert mgr._route_planning(state) == 'manager'

    def test_route_planning_end(self):
        mgr = MigrationManager(agents={})
        state = ProjectState(specs='x', tasks_approved=True)
        assert mgr._route_planning(state) == END
