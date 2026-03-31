import { CheckCircle, Circle, Loader } from 'lucide-react'

const PHASES = [
  { id: 'planning',    label: 'Planning' },
  { id: 'development', label: 'Development' },
  { id: 'integration', label: 'Integration' },
  { id: 'complete',    label: 'Finished' },
]

const ORDER = PHASES.map((p) => p.id)

export default function PhaseTracker({ currentPhase }) {
  const currentIdx = ORDER.indexOf(currentPhase)

  return (
    <div className="flex items-center gap-0">
      {PHASES.map(({ id, label }, i) => {
        const done = i < currentIdx
        const active = i === currentIdx
        const upcoming = i > currentIdx

        return (
          <div key={id} className="flex items-center">
            <div
              className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium
                ${done    ? 'bg-emerald-100 text-emerald-700' : ''}
                ${active  ? 'bg-blue-600 text-white shadow-sm' : ''}
                ${upcoming? 'bg-slate-200 text-slate-400' : ''}
              `}
            >
              {done    && <CheckCircle size={14} />}
              {active  && <Loader size={14} className="animate-spin" />}
              {upcoming && <Circle size={14} />}
              {label}
            </div>
            {i < PHASES.length - 1 && (
              <div className={`h-px w-6 ${done ? 'bg-emerald-400' : 'bg-slate-300'}`} />
            )}
          </div>
        )
      })}
    </div>
  )
}
