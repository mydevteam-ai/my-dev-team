import { useApp } from '../store.jsx'
import { Bot, ListChecks, RefreshCw } from 'lucide-react'

export default function NodeStatus() {
  const { state } = useApp()
  const { currentAgent, currentTaskName, currentTaskIndex, totalTasks, revisionCount, running } = state

  if (!currentAgent && !running) return null

  const progressPct = totalTasks > 0 ? Math.round((currentTaskIndex / totalTasks) * 100) : 0

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4 space-y-3">
      {/* Current agent */}
      <div className="flex items-center gap-2 text-sm">
        <Bot size={15} className="text-blue-500 shrink-0" />
        <span className="text-slate-500">Current node:</span>
        <span className="font-medium text-slate-800">
          {currentAgent || '—'}
        </span>
        {running && <span className="w-2 h-2 rounded-full bg-blue-400 pulse-dot ml-auto" />}
      </div>

      {/* Task progress */}
      {currentTaskName && (
        <div className="space-y-1.5">
          <div className="flex items-center gap-2 text-sm">
            <ListChecks size={14} className="text-slate-400 shrink-0" />
            <span className="text-slate-600 truncate flex-1">{currentTaskName}</span>
            {totalTasks > 0 && (
              <span className="text-xs text-slate-400 shrink-0">
                {currentTaskIndex}/{totalTasks}
              </span>
            )}
          </div>
          {totalTasks > 0 && (
            <div className="h-1.5 bg-slate-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 rounded-full transition-all duration-500"
                style={{ width: `${progressPct}%` }}
              />
            </div>
          )}
        </div>
      )}

      {/* Revision count */}
      {revisionCount > 0 && (
        <div className="flex items-center gap-2 text-xs text-amber-600">
          <RefreshCw size={12} />
          {revisionCount} revision{revisionCount > 1 ? 's' : ''}
        </div>
      )}
    </div>
  )
}
