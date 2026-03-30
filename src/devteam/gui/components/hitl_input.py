import streamlit as st


def render_hitl_input():
    """Render the HITL input area when the crew is waiting for human input."""
    if not st.session_state.get('hitl_pending'):
        return

    mode = st.session_state.get('hitl_mode', 'clarification')
    hitl_ext = st.session_state.get('hitl_extension')

    if mode == 'clarification':
        _render_clarification(hitl_ext)
    elif mode in ('approval_spec', 'approval_plan'):
        _render_approval(mode, hitl_ext)


def _clear_hitl():
    st.session_state['hitl_pending'] = False
    st.session_state['hitl_question'] = ''
    st.session_state['hitl_specs'] = ''
    st.session_state['hitl_tasks'] = []


def _render_clarification(hitl_ext):
    question = st.session_state.get('hitl_question', 'The team needs your input.')
    st.warning('🛑 **The crew needs your input before continuing.**')
    st.markdown(f"**Question:** {question}")

    answer = st.text_area(
        'Your Answer',
        key='hitl_answer_input',
        placeholder='Type your response here...',
    )

    col_submit, col_abort, _ = st.columns([1, 1, 3])
    with col_submit:
        if st.button('✅ Submit', type='primary', key='hitl_submit'):
            if answer.strip() and hitl_ext:
                hitl_ext.submit_response(answer.strip())
                _clear_hitl()
                st.rerun()
            elif not answer.strip():
                st.error('Please enter a response.')
    with col_abort:
        if st.button('❌ Abort', key='hitl_abort'):
            if hitl_ext:
                hitl_ext.abort()
                _clear_hitl()
                st.rerun()


def _render_approval(mode: str, hitl_ext):
    specs = st.session_state.get('hitl_specs', '')
    tasks = st.session_state.get('hitl_tasks', [])

    if mode == 'approval_spec':
        st.info('📄 **Specification Approval Required**')
        st.markdown('Review the Technical Specification produced by the Product Manager.')
        with st.expander('📄 Technical Specification', expanded=True):
            st.markdown(specs)
    else:
        st.info('📋 **Task Plan Approval Required**')
        st.markdown('Review the task plan produced by the System Architect.')
        with st.expander('📄 Technical Specification', expanded=False):
            st.markdown(specs)
        with st.expander('📝 Task Plan', expanded=True):
            for i, task in enumerate(tasks, 1):
                deps = ', '.join(task.get('dependencies', [])) or 'none'
                st.markdown(f"**{i}. {task['task_name']}**")
                st.markdown(f"- Story: {task['user_story']}")
                st.markdown(f"- Dependencies: {deps}")

    st.markdown('---')
    feedback = st.text_area(
        'Feedback (optional)',
        key='hitl_approval_feedback',
        placeholder='Leave blank to approve, or type feedback to request rework...',
    )

    col_approve, col_rework, col_abort, _ = st.columns([1, 1, 1, 2])
    with col_approve:
        if st.button('✅ Approve', type='primary', key='hitl_approve'):
            if hitl_ext:
                hitl_ext.submit_response('approved')
                _clear_hitl()
                st.rerun()
    with col_rework:
        if st.button('🔄 Request Rework', key='hitl_rework'):
            if feedback.strip() and hitl_ext:
                hitl_ext.submit_response(feedback.strip())
                _clear_hitl()
                st.rerun()
            elif not feedback.strip():
                st.error('Please provide feedback before requesting rework.')
    with col_abort:
        if st.button('❌ Abort', key='hitl_abort'):
            if hitl_ext:
                hitl_ext.abort()
                _clear_hitl()
                st.rerun()
