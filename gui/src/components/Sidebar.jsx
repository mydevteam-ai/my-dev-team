import { useApp } from '../store.jsx'
import {
  Home,
  FolderPlus,
  LayoutDashboard,
  RotateCcw,
  Clock,
} from 'lucide-react'

const NAV = [
  { id: 'welcome',     label: 'Welcome',            Icon: Home },
  { id: 'new-project', label: 'Start New Project',  Icon: FolderPlus },
  { id: 'dashboard',   label: 'Execution Dashboard', Icon: LayoutDashboard },
  { id: 'resume',      label: 'Resume Project',      Icon: RotateCcw },
  { id: 'history',     label: 'Show History',        Icon: Clock },
]

export default function Sidebar() {
  const { state, dispatch } = useApp()

  return (
    <aside className="w-60 shrink-0 bg-slate-800 text-slate-200 flex flex-col h-full">
      {/* Branding */}
      <div className="px-5 py-5 border-b border-slate-700">
        <div className="text-lg font-bold text-white leading-tight">🤖 My AI</div>
        <div className="text-sm text-slate-400">Dev Team</div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 space-y-1 px-2">
        {NAV.map(({ id, label, Icon }) => {
          const active = state.page === id
          return (
            <button
              key={id}
              onClick={() => dispatch({ type: 'NAVIGATE', page: id })}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors text-left
                ${active
                  ? 'bg-blue-600 text-white font-medium'
                  : 'text-slate-300 hover:bg-slate-700 hover:text-white'
                }`}
            >
              <Icon size={16} className="shrink-0" />
              <span>{label}</span>
            </button>
          )
        })}
      </nav>

      {/* Status indicator */}
      {state.running && (
        <div className="px-4 py-3 border-t border-slate-700 flex items-center gap-2 text-xs text-slate-400">
          <span className="w-2 h-2 rounded-full bg-green-400 pulse-dot" />
          Running…
        </div>
      )}
      {state.threadId && !state.running && (
        <div className="px-4 py-3 border-t border-slate-700 text-xs text-slate-500 truncate">
          {state.threadId}
        </div>
      )}
    </aside>
  )
}
