import { useState } from 'react'
import { useApp } from '../store.jsx'
import { FileCode, ChevronDown, ChevronRight, FolderOpen } from 'lucide-react'

const LANG_MAP = {
  py: 'python', js: 'javascript', ts: 'typescript', jsx: 'jsx', tsx: 'tsx',
  html: 'html', css: 'css', json: 'json', yaml: 'yaml', yml: 'yaml',
  md: 'markdown', sql: 'sql', toml: 'toml', sh: 'bash', txt: 'text',
}

function getExt(path) {
  return path.split('.').pop()?.toLowerCase() || ''
}

function FileItem({ path, content }) {
  const [open, setOpen] = useState(false)
  const ext = getExt(path)
  const lang = LANG_MAP[ext] || 'text'
  const lines = content.split('\n').length

  return (
    <div className="border-b border-slate-100 last:border-0">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-3 py-2 hover:bg-slate-50 transition-colors text-left"
      >
        {open ? <ChevronDown size={12} className="text-slate-400 shrink-0" /> : <ChevronRight size={12} className="text-slate-400 shrink-0" />}
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

export default function ArtifactsList() {
  const { state } = useApp()
  const files = state.workspaceFiles || {}
  const entries = Object.entries(files)

  return (
    <div className="bg-white border border-slate-200 rounded-xl h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-200 shrink-0">
        <FolderOpen size={15} className="text-amber-500" />
        <span className="text-sm font-medium text-slate-700">Workspace Files</span>
        {entries.length > 0 && (
          <span className="ml-auto text-xs text-slate-400 bg-slate-100 px-2 py-0.5 rounded-full">
            {entries.length}
          </span>
        )}
      </div>

      {/* File list */}
      <div className="flex-1 overflow-y-auto">
        {entries.length === 0 ? (
          <p className="text-slate-400 text-sm text-center py-8">No files yet</p>
        ) : (
          entries.map(([path, content]) => (
            <FileItem key={path} path={path} content={content} />
          ))
        )}
      </div>

      {/* Task summary */}
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
