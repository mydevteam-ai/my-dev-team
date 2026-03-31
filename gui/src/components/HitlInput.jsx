import { useState } from 'react'
import { useApp } from '../store.jsx'
import { api } from '../api'
import { AlertTriangle, Check, X, RefreshCw } from 'lucide-react'

function Section({ title, content }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="border border-slate-200 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-2.5 bg-slate-50 text-sm font-medium text-slate-700 hover:bg-slate-100"
      >
        {title}
        <span className="text-xs text-slate-400">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <pre className="text-xs text-slate-600 p-4 overflow-auto max-h-48 font-mono whitespace-pre-wrap bg-white">
          {content}
        </pre>
      )}
    </div>
  )
}

export default function HitlInput() {
  const { state, dispatch } = useApp()
  const [answer, setAnswer] = useState('')
  const [loading, setLoading] = useState(false)

  if (!state.hitlPending) return null

  const submit = async (response) => {
    setLoading(true)
    try {
      await api.submitHitl(state.threadId, { response })
      dispatch({ type: 'HITL_SUBMITTED' })
      setAnswer('')
    } catch (e) {
      alert(e.message)
    } finally {
      setLoading(false)
    }
  }

  const abort = async () => {
    setLoading(true)
    try {
      await api.submitHitl(state.threadId, { abort: true })
      dispatch({ type: 'HITL_SUBMITTED' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 space-y-4">
      <div className="flex items-center gap-2 text-amber-700 font-semibold text-sm">
        <AlertTriangle size={16} />
        {state.hitlMode === 'clarification' ? 'Clarification Required' : 'Approval Required'}
      </div>

      {/* Clarification */}
      {state.hitlMode === 'clarification' && (
        <>
          <p className="text-sm text-slate-700">{state.hitlQuestion}</p>
          <textarea
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            rows={3}
            placeholder="Your answer…"
            className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 resize-none"
          />
          <div className="flex gap-2">
            <button
              onClick={() => submit(answer)}
              disabled={!answer.trim() || loading}
              className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium disabled:opacity-50 hover:bg-blue-700"
            >
              <Check size={14} /> Submit
            </button>
            <button
              onClick={abort}
              disabled={loading}
              className="flex items-center gap-1.5 px-4 py-2 bg-red-100 text-red-600 rounded-lg text-sm hover:bg-red-200"
            >
              <X size={14} /> Abort
            </button>
          </div>
        </>
      )}

      {/* Spec / Plan approval */}
      {(state.hitlMode === 'approval_spec' || state.hitlMode === 'approval_plan') && (
        <>
          {state.hitlSpecs && <Section title="Technical Specification" content={state.hitlSpecs} />}
          {state.hitlMode === 'approval_plan' && state.hitlTasks?.length > 0 && (
            <Section
              title={`Task Plan (${state.hitlTasks.length} tasks)`}
              content={state.hitlTasks.map((t, i) =>
                `${i + 1}. ${t.task_name}\n   ${t.user_story}\n   Dependencies: ${t.dependencies?.join(', ') || 'none'}`
              ).join('\n\n')}
            />
          )}
          <textarea
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            rows={2}
            placeholder="Optional feedback if requesting rework…"
            className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 resize-none"
          />
          <div className="flex gap-2 flex-wrap">
            <button
              onClick={() => submit('approved')}
              disabled={loading}
              className="flex items-center gap-1.5 px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700"
            >
              <Check size={14} /> Approve
            </button>
            <button
              onClick={() => submit(answer || 'Please rework.')}
              disabled={loading}
              className="flex items-center gap-1.5 px-4 py-2 bg-amber-100 text-amber-700 rounded-lg text-sm hover:bg-amber-200"
            >
              <RefreshCw size={14} /> Request Rework
            </button>
            <button
              onClick={abort}
              disabled={loading}
              className="flex items-center gap-1.5 px-4 py-2 bg-red-100 text-red-600 rounded-lg text-sm hover:bg-red-200"
            >
              <X size={14} /> Abort
            </button>
          </div>
        </>
      )}
    </div>
  )
}
