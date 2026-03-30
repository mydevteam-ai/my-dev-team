import warnings
warnings.filterwarnings('ignore', message="Core Pydantic V1 functionality", category=UserWarning)

import streamlit as st
from devteam.utils import setup_logging
from devteam.gui.session import drain_queue, init_session_state
from devteam.gui import views

@st.cache_resource
def _init_logging():
    setup_logging(console_level=None)

_init_logging()

def main():
    st.set_page_config(page_title='My AI Dev Team', page_icon='🚀', layout='wide')
    st.markdown('<style>.block-container { padding-top: 1rem; }</style>', unsafe_allow_html=True)
    init_session_state()

    nav_options = [
        '🏠 Welcome',
        '🚀 Start New Project',
        '📊 Execution Dashboard',
        '🔄 Resume Project',
        '🕰️ Show History',
    ]

    st.title('🤖 My AI Dev Team')
    st.sidebar.title('Navigation')

    if 'nav_mode' not in st.session_state:
        st.session_state['nav_mode'] = '🏠 Welcome'

    if 'nav_mode_selector' not in st.session_state or st.session_state['nav_mode_selector'] not in nav_options:
        st.session_state['nav_mode_selector'] = st.session_state['nav_mode']

    requested_mode = st.session_state.pop('requested_mode', None)
    if requested_mode in nav_options:
        st.session_state['nav_mode'] = requested_mode
        st.session_state['nav_mode_selector'] = requested_mode

    if st.session_state.get('execution_active') and st.session_state.get('nav_mode') != '📊 Execution Dashboard':
        st.session_state['nav_mode'] = '📊 Execution Dashboard'
        st.session_state['nav_mode_selector'] = '📊 Execution Dashboard'
        st.rerun()

    mode = st.sidebar.radio('Choose an action:', nav_options, key='nav_mode_selector')
    st.session_state['nav_mode'] = mode

    if st.session_state.get('execution_active') or st.session_state.get('event_queue') is not None:
        drain_queue()
        worker = st.session_state.get('worker_thread')
        if worker and not worker.is_alive():
            drain_queue()
            st.session_state['execution_active'] = False

    if mode == '🏠 Welcome':
        views.render_welcome_page()
    elif mode == '🚀 Start New Project':
        views.render_start_new_project_page()
    elif mode == '📊 Execution Dashboard':
        views.render_execution_dashboard_page()
    elif mode == '🔄 Resume Project':
        views.render_resume_project_page()
    elif mode == '🕰️ Show History':
        views.render_history_page()

if __name__ == '__main__':
    main()
