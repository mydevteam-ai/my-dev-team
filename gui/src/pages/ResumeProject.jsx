import { useEffect, useState } from 'react'
import { useApp } from '../store.jsx'
import { api } from '../api'
import { RotateCcw, ChevronDown } from 'lucide-react'

function Select({ label, value, onChange, options, placeholder }) {
  return (
    <div className="space-y-1.5">
      <label className="text-sm font-medium text-slate-700">{label}</label>
      <div className="relative">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full appearance-none bg-white border border-slate-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 pr-8"
        >
          {placeholder && <option value="">{placeholder}</option>}
          {options.map((o) => <option key={o} value={o}>{o}</option>)}
        </select>
        <ChevronDown size={14} className="absolute right-3 top-3 text-slate-400 pointer-events-none" />
      </div>
    </div>
  )
}

export default function ResumeProject() {
  const { dispatch } = useApp()
  const [threads, setThreads] = useState([])
  const [threadId, setThreadId] = useState('')
  const [feedback, setFeedback] = useState('')
  const [feedbackSource, setFeedbackSource] = useState('reviewer')
  const [checkpointId, setCheckpointId] = useState('')
  const [askApproval, setAskApproval] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.getThreads().then(setThreads).catch(() => {})
  }, [])

  const resume = async () => {
    if (!threadId) { setError('Select a project to resume.'); return }
    setError(null)
    setLoading(true)
    try {
      await api.resumeProject(threadId, {
        feedback,
        feedback_source: feedbackSource,
        checkpoint_id: checkpointId || null,
        ask_approval: askApproval,
      })
      dispatch({ type: 'SET_THREAD', threadId })
    } catch (e) {
      setError(e.message)
      setLoading(false)
    }
  }

  return (
    <div className="max-w-xl mx-auto px-6 py-10 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Resume Project</h1>
        <p className="text-slate-500 text-sm mt-1">Pick up a previous run, optionally injecting feedback.</p>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-4">
        <Select
          label="Project"
          value={threadId}
          onChange={setThreadId}
          options={threads}
          placeholder="— select a project —"
        />

        <div className="space-y-1.5">
          <label className="text-sm font-medium text-slate-700">Feedback (optional)</label>
          <textarea
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            rows={3}
            placeholder="Enter feedback to inject into the workflow…"
            className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 resize-none"
          />
        </div>

        <Select
          label="Deliver feedback as"
          value={feedbackSource}
          onChange={setFeedbackSource}
          options={['reviewer', 'qa', 'pm', 'architect']}
        />

        <div className="space-y-1.5">
          <label className="text-sm font-medium text-slate-700">Checkpoint ID (optional)</label>
          <input
            type="text"
            value={checkpointId}
            onChange={(e) => setCheckpointId(e.target.value)}
            placeholder="Leave blank to use latest checkpoint"
            className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
        </div>

        <label className="flex items-center gap-2 cursor-pointer text-sm text-slate-700">
          <input
            type="checkbox"
            checked={askApproval}
            onChange={(e) => setAskApproval(e.target.checked)}
            className="w-4 h-4 rounded accent-blue-600"
          />
          Ask for approval
        </label>
      </div>

      {error && (
        <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-2">{error}</p>
      )}

      <button
        onClick={resume}
        disabled={loading || !threadId}
        className="w-full flex items-center justify-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-xl font-semibold text-sm hover:bg-blue-700 disabled:opacity-50 transition-colors"
      >
        <RotateCcw size={16} />
        {loading ? 'Resuming…' : 'Resume Project'}
      </button>
    </div>
  )
}
