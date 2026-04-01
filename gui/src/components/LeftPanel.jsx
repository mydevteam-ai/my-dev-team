import { useState } from 'react'
import { useApp } from '../store.jsx'
import { FolderOpen, FileText, Code, ListChecks, ChevronDown, ChevronRight, FileCode, CheckCircle, XCircle, Circle } from 'lucide-react'
import Markdown from './Markdown'

// ── Workspace tab ────────────────────────────────────────────────────────────

function FileItem({ path, content }) {
  const [open, setOpen] = useState(false)
  const lines = content.split('\n').length

  return (
    <div className="border-b border-slate-100 last:border-0">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-3 py-2 hover:bg-slate-50 transition-colors text-left"
      >
        {open
          ? <ChevronDown size={12} className="text-slate-400 shrink-0" />
          : <ChevronRight size={12} className="text-slate-400 shrink-0" />}
        <FileCode size={13} className="text-blue-400 shrink-0" />
        <span className="text-sm text-slate-700 flex-1 truncate font-mono">{path}</span>
        <span className="text-xs text-slate-400 shrink-0">{lines}L</span>
      </button>
      {open && (
        <div className="bg-slate-900 mx-2 mb-2 rounded-lg overflow-auto max-h-64">
          <pre className="text-xs text-slate-200 p-3 font-mono leading-relaxed whitespace-pre">
            {content}
          </pre>
        </div>
      )}
    </div>
  )
}

function WorkspaceTab() {
  const { state } = useApp()
  const entries = Object.entries(state.workspaceFiles || {})

  return (
    <div className="flex-1 overflow-y-auto flex flex-col min-h-0">
      <div className="flex-1 overflow-y-auto">
        {entries.length === 0
          ? <p className="text-slate-400 text-sm text-center py-8">No files yet</p>
          : entries.map(([path, content]) => (
              <FileItem key={path} path={path} content={content} />
            ))
        }
      </div>
      {(state.completedTasks.length > 0 || state.failedTasks.length > 0) && (
        <div className="border-t border-slate-200 px-4 py-2 flex gap-3 text-xs shrink-0">
          {state.completedTasks.length > 0 && (
            <span className="text-emerald-600">✓ {state.completedTasks.length} done</span>
          )}
          {state.failedTasks.length > 0 && (
            <span className="text-red-500">✗ {state.failedTasks.length} failed</span>
          )}
        </div>
      )}
    </div>
  )
}

// ── Specs tab ────────────────────────────────────────────────────────────────

function SpecsTab() {
  const { state } = useApp()
  return (
    <div className="flex-1 overflow-y-auto p-4">
      {state.specs
        ? <Markdown>{state.specs}</Markdown>
        : <p className="text-slate-400 text-sm text-center py-8">Specifications will appear here</p>
      }
    </div>
  )
}

// ── Report tab ───────────────────────────────────────────────────────────────

function ReportTab() {
  const { state } = useApp()
  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {state.finalReport
        ? <Markdown>{state.finalReport}</Markdown>
        : <p className="text-slate-400 text-sm text-center py-8">Final report will appear here</p>
      }
      {state.integrationBugs?.length > 0 && (
        <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg">
          <p className="text-xs font-semibold text-amber-700 mb-2">Integration issues:</p>
          <ul className="list-disc list-inside space-y-1">
            {state.integrationBugs.map((b, i) => (
              <li key={i} className="text-xs text-amber-600">{b}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

// ── Tasks tab ────────────────────────────────────────────────────────────────

function TaskItem({ task, completed, failed }) {
  const [open, setOpen] = useState(false)
  const { task_name, user_story, acceptance_criteria = [], dependencies = [] } = task

  const StatusIcon = completed ? CheckCircle : failed ? XCircle : Circle
  const statusColor = completed ? 'text-emerald-500' : failed ? 'text-red-400' : 'text-slate-300'
  const badge = completed ? 'bg-emerald-50 text-emerald-700' : failed ? 'bg-red-50 text-red-600' : 'bg-slate-100 text-slate-500'
  const badgeLabel = completed ? 'done' : failed ? 'failed' : 'pending'

  return (
    <div className="border-b border-slate-100 last:border-0">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-start gap-2 px-3 py-2.5 hover:bg-slate-50 transition-colors text-left"
      >
        <StatusIcon size={14} className={`${statusColor} shrink-0 mt-0.5`} />
        <span className="text-sm text-slate-700 flex-1 leading-snug">{task_name}</span>
        <span className={`text-xs px-1.5 py-0.5 rounded-full shrink-0 ${badge}`}>{badgeLabel}</span>
        {open ? <ChevronDown size={12} className="text-slate-400 shrink-0 mt-0.5" /> : <ChevronRight size={12} className="text-slate-400 shrink-0 mt-0.5" />}
      </button>
      {open && (
        <div className="px-4 pb-3 space-y-2 text-xs text-slate-600">
          {user_story && <Markdown className="text-xs">{user_story}</Markdown>}
          {acceptance_criteria.length > 0 && (
            <div>
              <p className="font-semibold text-slate-500 mb-1">Acceptance criteria</p>
              <ul className="space-y-0.5 list-disc list-inside">
                {acceptance_criteria.map((c, i) => <li key={i}>{c}</li>)}
              </ul>
            </div>
          )}
          {dependencies.length > 0 && (
            <p className="text-slate-400">Depends on: {dependencies.join(', ')}</p>
          )}
        </div>
      )}
    </div>
  )
}

function TasksTab() {
  const { state } = useApp()
  const { pendingTasks, completedTasks, failedTasks } = state
  const completedSet = new Set(completedTasks)
  const failedSet = new Set(failedTasks)

  if (pendingTasks.length === 0) {
    return <p className="text-slate-400 text-sm text-center py-8">Tasks will appear here after planning</p>
  }

  return (
    <div className="flex-1 overflow-y-auto flex flex-col min-h-0">
      <div className="flex-1 overflow-y-auto">
        {pendingTasks.map((task, i) => (
          <TaskItem
            key={i}
            task={task}
            completed={completedSet.has(task.task_name)}
            failed={failedSet.has(task.task_name)}
          />
        ))}
      </div>
      <div className="border-t border-slate-200 px-4 py-2 flex gap-3 text-xs shrink-0">
        <span className="text-slate-400">{pendingTasks.length} tasks total</span>
        {completedTasks.length > 0 && <span className="text-emerald-600">✓ {completedTasks.length} done</span>}
        {failedTasks.length > 0 && <span className="text-red-500">✗ {failedTasks.length} failed</span>}
      </div>
    </div>
  )
}

// ── Composed panel ───────────────────────────────────────────────────────────

const TABS = [
  { id: 'workspace', label: 'Workspace', Icon: FolderOpen },
  { id: 'tasks',     label: 'Tasks',     Icon: ListChecks },
  { id: 'specs',     label: 'Specs',     Icon: FileText },
  { id: 'report',    label: 'Report',    Icon: Code },
]

export default function LeftPanel() {
  const { state } = useApp()
  const [tab, setTab] = useState('workspace')
  const fileCount = Object.keys(state.workspaceFiles || {}).length
  const taskCount = state.pendingTasks.length

  return (
    <div className="bg-white border border-slate-200 rounded-xl flex flex-col h-full overflow-hidden">
      {/* Tab bar */}
      <div className="flex border-b border-slate-200 px-2 shrink-0">
        {TABS.map(({ id, label, Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex items-center gap-1.5 px-3 py-2 text-sm border-b-2 transition-colors
              ${tab === id
                ? 'border-blue-500 text-blue-600 font-medium'
                : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
          >
            <Icon size={13} />
            {label}
            {id === 'workspace' && fileCount > 0 && (
              <span className="text-xs bg-slate-100 text-slate-500 px-1.5 rounded-full">{fileCount}</span>
            )}
            {id === 'tasks' && taskCount > 0 && (
              <span className="text-xs bg-slate-100 text-slate-500 px-1.5 rounded-full">{taskCount}</span>
            )}
          </button>
        ))}
      </div>

      {tab === 'workspace' && <WorkspaceTab />}
      {tab === 'tasks'     && <TasksTab />}
      {tab === 'specs'     && <SpecsTab />}
      {tab === 'report'    && <ReportTab />}
    </div>
  )
}
