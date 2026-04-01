import { useApp } from '../store.jsx'
import PhaseTracker from '../components/PhaseTracker'
import NodeStatus from '../components/NodeStatus'
import LeftPanel from '../components/LeftPanel'
import ChatWindow from '../components/ChatWindow'
import HitlInput from '../components/HitlInput'
import { CheckCircle, XCircle, AlertTriangle, LayoutDashboard } from 'lucide-react'

function Banner({ type, message }) {
  const styles = {
    success: 'bg-emerald-50 border-emerald-300 text-emerald-800',
    error:   'bg-red-50 border-red-300 text-red-800',
    abort:   'bg-amber-50 border-amber-300 text-amber-800',
  }
  const icons = {
    success: <CheckCircle size={16} />,
    error:   <XCircle size={16} />,
    abort:   <AlertTriangle size={16} />,
  }
  return (
    <div className={`flex items-center gap-2 border rounded-xl px-4 py-3 text-sm font-medium ${styles[type]}`}>
      {icons[type]}
      {message}
    </div>
  )
}

export default function Dashboard() {
  const { state } = useApp()

  const hasData = state.threadId || state.communicationLog.length > 0

  return (
    <div className="h-full flex flex-col p-5 gap-4">
      {/* Header */}
      <div className="flex items-center gap-3 shrink-0">
        <LayoutDashboard size={18} className="text-slate-500" />
        <h1 className="text-lg font-bold text-slate-900">Execution Dashboard</h1>
        {state.threadId && (
          <span className="text-xs text-slate-400 bg-slate-200 px-2 py-0.5 rounded-full font-mono">
            {state.threadId}
          </span>
        )}
      </div>

      {/* Empty state */}
      {!hasData && (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center space-y-2">
            <p className="text-slate-400 text-sm">No active execution.</p>
            <p className="text-slate-400 text-xs">Start a new project or resume an existing one.</p>
          </div>
        </div>
      )}

      {hasData && (
        <>
          {/* Phase tracker */}
          <div className="shrink-0">
            <PhaseTracker currentPhase={state.currentPhase} />
          </div>

          {/* Completion / error banners */}
          {!state.running && state.threadId && (
            <>
              {state.aborted && <Banner type="abort" message="Workflow was aborted." />}
              {state.error && !state.aborted && <Banner type="error" message={state.error} />}
              {!state.error && !state.aborted && state.currentPhase === 'complete' && (
                <Banner type="success" message="🎉 Project completed successfully!" />
              )}
            </>
          )}

          {/* HITL */}
          {state.hitlPending && (
            <div className="shrink-0">
              <HitlInput />
            </div>
          )}

          {/* Node status */}
          <div className="shrink-0">
            <NodeStatus />
          </div>

          {/* Main grid: artifacts + chat */}
          <div className="flex-1 grid grid-cols-5 gap-4 min-h-0">
            {/* Left: workspace / specs / report */}
            <div className="col-span-2 min-h-0">
              <LeftPanel />
            </div>
            {/* Right: chat / log */}
            <div className="col-span-3 min-h-0">
              <ChatWindow />
            </div>
          </div>
        </>
      )}
    </div>
  )
}
