import logging
from queue import Empty
import streamlit as st
from devteam.crew.events import Event

AGENT_META = {
    'pm': {'icon': '📋', 'label': 'Product Manager', 'phase': 'Planning'},
    'architect': {'icon': '🏗️', 'label': 'System Architect', 'phase': 'Planning'},
    'human': {'icon': '👤', 'label': 'Human Input', 'phase': 'Planning'},
    'developer': {'icon': '💻', 'label': 'Senior Developer', 'phase': 'Development'},
    'reviewer': {'icon': '🔍', 'label': 'Code Reviewer', 'phase': 'Development'},
    'qa': {'icon': '🧪', 'label': 'QA Engineer', 'phase': 'Development'},
    'manager': {'icon': '🔀', 'label': 'Task Router', 'phase': 'Development'},
    'reporter': {'icon': '📝', 'label': 'Reporter', 'phase': 'Integration'},
    'final_qa': {'icon': '✅', 'label': 'Final QA', 'phase': 'Integration'},
}

def init_session_state():
    defaults = {
        'execution_active': False,
        'events': [],
        'current_phase': None,
        'active_agents': [],
        'task_progress': {'current': 0, 'total': 0, 'name': ''},
        'communication_log': [],
        'workspace_files': {},
        'specs': '',
        'final_report': '',
        'result_holder': {},
        'event_queue': None,
        'worker_thread': None,
        'revision_count': 0,
        'crew_started': False,
        'hitl_pending': False,
        'hitl_mode': 'clarification',
        'hitl_question': '',
        'hitl_specs': '',
        'hitl_tasks': [],
        'hitl_extension': None,
        'thinking_text': '',
        'thinking_active': False,
        'thinking_enabled': False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def reset_execution_state():
    for key in ['events', 'active_agents', 'communication_log', 'workspace_files', 'specs', 'final_report', 'result_holder']:
        st.session_state[key] = [] if key in ('events', 'active_agents', 'communication_log') else ({} if key in ('workspace_files', 'result_holder') else '')
    st.session_state['task_progress'] = {'current': 0, 'total': 0, 'name': ''}
    st.session_state['revision_count'] = 0
    st.session_state['crew_started'] = False
    st.session_state['current_phase'] = 'Planning'
    st.session_state['execution_active'] = True
    st.session_state['thinking_text'] = ''
    st.session_state['thinking_active'] = False

def process_event(event: dict):
    event_type = event['type']

    if event_type == 'thinking_token':
        token = event.get('token', '')
        is_thinking = event.get('is_thinking', False)
        if is_thinking:
            if not st.session_state.get('thinking_active'):
                st.session_state['thinking_active'] = True
                st.session_state['thinking_text'] += '\n---\n'
            st.session_state['thinking_text'] += token
        else:
            st.session_state['thinking_active'] = False
        return

    st.session_state['events'].append(event)

    if event_type == 'start':
        st.session_state['current_phase'] = 'Planning'
        st.session_state['crew_started'] = True
        return

    if event_type == 'step':
        _process_step_event(event)
        return

    if event_type == 'pause':
        return

    if event_type == 'hitl_request':
        st.session_state['hitl_pending'] = True
        st.session_state['hitl_mode'] = event.get('mode', 'clarification')
        st.session_state['hitl_question'] = event.get('question', '')
        st.session_state['hitl_specs'] = event.get('specs', '')
        st.session_state['hitl_tasks'] = event.get('pending_tasks', [])
        return

    if event_type in ('finish', 'error'):
        st.session_state['execution_active'] = False
        if event_type == 'finish':
            st.session_state['current_phase'] = 'Complete'
            final = event.get('state', {})
            if final.get('final_report'):
                st.session_state['final_report'] = final['final_report']

def drain_queue() -> bool:
    queue = st.session_state.get('event_queue')
    if queue is None:
        return False
    had_events = False
    while True:
        try:
            event = queue.get_nowait()
            had_events = True
            process_event(event)
        except Empty:
            break
    if had_events:
        logging.debug('Drained %d total events from queue', len(st.session_state.get('events', [])))
    return had_events

def _process_step_event(event: dict):
    state_update = event.get('state_update', {})
    full_state = event.get('full_state', {})
    for node_name, node_output in state_update.items():
        meta = AGENT_META.get(node_name, {'icon': '⚙️', 'label': node_name, 'phase': 'Unknown'})
        st.session_state['current_phase'] = meta['phase']
        st.session_state['active_agents'].append(
            {
                'node': node_name,
                'label': meta['label'],
                'icon': meta['icon'],
                'phase': meta['phase'],
                'ts': event['ts'],
                'output_keys': list(node_output.keys()) if isinstance(node_output, dict) else [],
            }
        )
        if isinstance(node_output, dict):
            if 'specs' in node_output and node_output['specs']:
                st.session_state['specs'] = node_output['specs']
            if 'workspace_files' in node_output and node_output['workspace_files']:
                st.session_state['workspace_files'] = node_output['workspace_files']
            if 'final_report' in node_output and node_output['final_report']:
                st.session_state['final_report'] = node_output['final_report']
            if 'revision_count' in node_output:
                st.session_state['revision_count'] = node_output['revision_count']
    pending = full_state.get('pending_tasks', [])
    current_phase = full_state.get('current_phase', '')
    if pending:
        completed = full_state.get('completed_tasks', [])
        st.session_state['task_progress'] = {
            'current': len(completed),
            'total': len(pending),
            'name': full_state.get('current_task_name', ''),
        }
    if current_phase in ('integration', 'complete'):
        st.session_state['current_phase'] = 'Integration'
    st.session_state['communication_log'] = full_state.get('communication_log', [])
