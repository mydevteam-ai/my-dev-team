import { useApp } from '../store.jsx'
import { BarChart3, AlertTriangle } from 'lucide-react'

const KIND_LABELS = {
  thrashing: '⚠️ Thrashing',
  context_bloat: '📈 Context Bloat',
  high_waste: '🗑️ High Waste',
  context_pressure: '🪟 Context Pressure',
  output_repair: '🔧 Output Repair',
}

function Stat({ label, value }) {
  return (
    <div className="flex flex-col items-center px-3">
      <span className="text-[11px] uppercase tracking-wide text-slate-400">{label}</span>
      <span className="text-sm font-bold text-slate-700 font-mono">{value}</span>
    </div>
  )
}

export default function TelemetryPanel() {
  const { state } = useApp()
  const t = state.telemetry
  if (!t) return null

  const fmt = (n) => (n ?? 0).toLocaleString()

  return (
    <div className="bg-white border border-slate-200 rounded-xl px-4 py-3 space-y-2">
      <div className="flex items-center gap-2">
        <BarChart3 size={14} className="text-blue-500" />
        <span className="text-sm font-semibold text-slate-700">Telemetry & Cost</span>
        <div className="ml-auto flex divide-x divide-slate-200">
          <Stat label="Requests" value={fmt(t.totalRequests)} />
          <Stat label="Repaired" value={fmt(t.repairedCalls)} />
          <Stat label="Prompt" value={fmt(t.inputTokens)} />
          <Stat label="Cached" value={fmt(t.cachedTokens)} />
          <Stat label="Completion" value={fmt(t.outputTokens)} />
          <Stat label="Total" value={fmt(t.totalTokens)} />
          <Stat label="Est. Cost" value={`$${(t.totalCost ?? 0).toFixed(4)}`} />
        </div>
      </div>

      {t.diagnostics.length > 0 && (
        <div className="border-t border-slate-100 pt-2 space-y-1">
          {t.diagnostics.map((d, i) => (
            <div key={i} className="flex items-start gap-2 text-xs text-amber-700">
              <AlertTriangle size={12} className="mt-0.5 shrink-0 text-amber-500" />
              <span>
                <span className="font-semibold">{KIND_LABELS[d.kind] || d.kind}</span>
                {' · '}
                <span className="font-mono">{d.agent}</span>
                {' — '}
                {d.detail}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
