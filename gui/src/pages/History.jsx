import { useEffect, useState } from 'react'
import { api } from '../api'
import { Clock, ChevronDown } from 'lucide-react'

export default function History() {
  const [threads, setThreads] = useState([])
  const [threadId, setThreadId] = useState('')
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.getThreads().then(setThreads).catch(() => {})
  }, [])

  const load = async () => {
    if (!threadId) return
    setLoading(true)
    setError(null)
    try {
      const data = await api.getHistory(threadId)
      setHistory(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto px-6 py-10 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Project History</h1>
        <p className="text-slate-500 text-sm mt-1">Browse checkpoint timeline for a project.</p>
      </div>

      <div className="flex gap-3">
        <div className="relative flex-1">
          <select
            value={threadId}
            onChange={(e) => setThreadId(e.target.value)}
            className="w-full appearance-none bg-white border border-slate-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 pr-8"
          >
            <option value="">— select a project —</option>
            {threads.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <ChevronDown size={14} className="absolute right-3 top-3 text-slate-400 pointer-events-none" />
        </div>
        <button
          onClick={load}
          disabled={!threadId || loading}
          className="px-4 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {loading ? 'Loading…' : 'Load'}
        </button>
      </div>

      {error && (
        <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-2">{error}</p>
      )}

      {history.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-200">
            <Clock size={14} className="text-slate-400" />
            <span className="text-sm font-medium text-slate-700">
              {history.length} checkpoint{history.length !== 1 ? 's' : ''}
            </span>
          </div>
          <div className="divide-y divide-slate-100">
            {history.map((cp, i) => (
              <div key={cp.c_id} className="flex items-start gap-4 px-4 py-3">
                {/* Timeline dot */}
                <div className="flex flex-col items-center pt-1">
                  <div className={`w-2.5 h-2.5 rounded-full shrink-0 ${i === 0 ? 'bg-blue-500' : 'bg-slate-300'}`} />
                  {i < history.length - 1 && <div className="w-px flex-1 bg-slate-200 mt-1" style={{ minHeight: 16 }} />}
                </div>
                <div className="flex-1 min-w-0 space-y-0.5">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-slate-700">{cp.node}</span>
                    {i === 0 && (
                      <span className="text-xs bg-blue-100 text-blue-600 px-1.5 py-0.5 rounded">latest</span>
                    )}
                  </div>
                  <p className="text-xs text-slate-400 font-mono truncate">{cp.c_id}</p>
                  <p className="text-xs text-slate-400">
                    {new Date(cp.time).toLocaleString()}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
