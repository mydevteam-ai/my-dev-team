import threading
import time
from queue import Queue
import streamlit as st
from devteam import settings
from devteam.gui.execution import get_providers_from_config, run_crew_in_thread
from devteam.gui.session import reset_execution_state
from devteam.utils import parse_spec_from_string
from devteam.extensions.hitl_gui import HumanInTheLoopGUI

def render_start_new_project_page():
    st.header('Start a New Project')

    if st.session_state.get('execution_active', False):
        st.info('Execution is currently running. Open the dashboard to monitor progress.')
        st.button('📊 Open Execution Dashboard', key='open_dashboard_while_running',
                  on_click=lambda: st.session_state.update({'requested_mode': '📊 Execution Dashboard'}))
        return

    uploaded_file = st.file_uploader('Upload your project requirements (.txt)', type=['txt'])
    col_left, col_right = st.columns(2, gap='large')
    with col_left:
        available_providers = get_providers_from_config()
        provider = st.selectbox('LLM Provider', available_providers)
        rpm = st.number_input('Rate Limit (RPM, 0 = unlimited)', min_value=0, value=0, step=10)
        timeout = st.number_input('LLM Timeout (seconds)', min_value=10, value=120, step=10)
    with col_right:
        st.markdown('<div style="height: 1.9rem"></div>', unsafe_allow_html=True)
        thinking = st.checkbox('🧠 Enable Thinking Stream', help='Stream LLM reasoning/thinking tokens in real-time on the dashboard.')
        ask_approval = st.checkbox('✋ Ask for approval', help='Pause and ask for your approval before proceeding from planning to development.')

    if uploaded_file and st.button('🚀 Launch AI Team', type='primary'):
        content = uploaded_file.read().decode('utf-8')
        project_name, requirements = parse_spec_from_string(content)

        settings.llm_timeout = timeout
        settings.ask_approval = ask_approval
        reset_execution_state()
        st.session_state['thinking_enabled'] = thinking

        event_queue = Queue()
        st.session_state['event_queue'] = event_queue
        result_holder = {}
        st.session_state['result_holder'] = result_holder

        hitl_ext = HumanInTheLoopGUI(event_queue)
        st.session_state['hitl_extension'] = hitl_ext

        worker = threading.Thread(
            target=run_crew_in_thread,
            args=(project_name, requirements, provider, rpm, event_queue, result_holder, hitl_ext, thinking),
            daemon=True,
        )
        st.session_state['worker_thread'] = worker
        worker.start()

        st.toast(f"🚀 AI Team launched for '{project_name}'!", icon='🤖')
        time.sleep(0.5)
        st.rerun()
