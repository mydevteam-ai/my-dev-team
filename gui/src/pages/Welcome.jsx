import { useApp } from '../store.jsx'
import { FolderPlus, LayoutDashboard, RotateCcw, Zap, Bot, GitMerge } from 'lucide-react'

function Card({ Icon, title, desc, action, page, dispatch }) {
  return (
    <button
      onClick={() => dispatch({ type: 'NAVIGATE', page })}
      className="group bg-white border border-slate-200 rounded-xl p-6 text-left hover:border-blue-400 hover:shadow-md transition-all space-y-3"
    >
      <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center group-hover:bg-blue-100 transition-colors">
        <Icon size={20} className="text-blue-600" />
      </div>
      <div>
        <p className="font-semibold text-slate-800">{title}</p>
        <p className="text-sm text-slate-500 mt-1">{desc}</p>
      </div>
      <p className="text-xs text-blue-600 font-medium">{action} →</p>
    </button>
  )
}

function FeatureRow({ Icon, title, desc }) {
  return (
    <div className="flex items-start gap-3">
      <div className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center shrink-0 mt-0.5">
        <Icon size={14} className="text-slate-500" />
      </div>
      <div>
        <p className="text-sm font-medium text-slate-700">{title}</p>
        <p className="text-xs text-slate-500 mt-0.5">{desc}</p>
      </div>
    </div>
  )
}

export default function Welcome() {
  const { dispatch } = useApp()

  return (
    <div className="max-w-3xl mx-auto px-6 py-10 space-y-10">
      {/* Hero */}
      <div className="space-y-3">
        <div className="text-4xl">🤖</div>
        <h1 className="text-3xl font-bold text-slate-900">My AI Dev Team</h1>
        <p className="text-slate-600 text-lg leading-relaxed max-w-xl">
          An autonomous, LangGraph-powered development agency. Describe your project and watch a
          full team of AI agents — PM, Architect, Developer, Reviewer, and QA — build it for you.
        </p>
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card
          Icon={FolderPlus}
          title="New Project"
          desc="Upload requirements and kick off a fresh development run."
          action="Get started"
          page="new-project"
          dispatch={dispatch}
        />
        <Card
          Icon={LayoutDashboard}
          title="Dashboard"
          desc="Monitor the live execution of the current project."
          action="Open dashboard"
          page="dashboard"
          dispatch={dispatch}
        />
        <Card
          Icon={RotateCcw}
          title="Resume Work"
          desc="Pick up a previous project with optional feedback."
          action="Resume"
          page="resume"
          dispatch={dispatch}
        />
      </div>

      {/* How it works */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-slate-800">How it works</h2>
        <div className="grid gap-4">
          <FeatureRow
            Icon={Bot}
            title="Multi-agent pipeline"
            desc="PM refines requirements → Architect designs tasks → parallel Developer/Reviewer/QA loops → Integration → Report."
          />
          <FeatureRow
            Icon={Zap}
            title="Live execution dashboard"
            desc="Watch the thinking process and agent outputs stream in real time."
          />
          <FeatureRow
            Icon={GitMerge}
            title="Human in the loop"
            desc="Optionally review and approve the specification and task plan before development starts."
          />
        </div>
      </div>
    </div>
  )
}
