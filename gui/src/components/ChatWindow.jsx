import { useEffect, useRef, useState } from 'react'
import { useApp } from '../store.jsx'
import { MessageSquare, Brain, FileText, Code } from 'lucide-react'

function Tab({ id, label, Icon, active, onClick }) {
  return (
    <button
      onClick={() => onClick(id)}
      className={`flex items-center gap-1.5 px-3 py-2 text-sm border-b-2 transition-colors
        ${active
          ? 'border-blue-500 text-blue-600 font-medium'
          : 'border-transparent text-slate-500 hover:text-slate-700'
        }`}
    >
      <Icon size={13} />
      {label}
    </button>
  )
}

function LogEntry({ text }) {
  const lines = text.split('\n')
  const title = lines[0] || ''
  const body = lines.slice(1).join('\n').trim()
  return (
    <div className="border-b border-slate-100 last:border-0 py-3 px-4">
      <p className="text-sm font-medium text-slate-700">{title}</p>
      {body && <p className="text-xs text-slate-500 mt-1 whitespace-pre-wrap">{body}</p>}
    </div>
  )
}

export default function ChatWindow() {
  const { state } = useApp()
  const [tab, setTab] = useState('log')
  const logEndRef = useRef(null)
  const thinkRef = useRef(null)

  // Auto-scroll communication log
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [state.communicationLog.length])

  // Auto-scroll thinking
  useEffect(() => {
    if (thinkRef.current) {
      thinkRef.current.scrollTop = thinkRef.current.scrollHeight
    }
  }, [state.thinkingText])

  const tabs = [
    { id: 'log',     label: 'Activity',  Icon: MessageSquare },
    { id: 'thinking',label: 'Thinking',  Icon: Brain },
    { id: 'specs',   label: 'Specs',     Icon: FileText },
    { id: 'report',  label: 'Report',    Icon: Code },
  ]

  return (
    <div className="bg-white border border-slate-200 rounded-xl flex flex-col h-full overflow-hidden">
      {/* Tab bar */}
      <div className="flex border-b border-slate-200 px-2 shrink-0">
        {tabs.map((t) => (
          <Tab key={t.id} {...t} active={tab === t.id} onClick={setTab} />
        ))}
        {state.thinkingActive && (
          <span className="ml-auto self-center mr-2 text-xs text-purple-500 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-purple-400 pulse-dot" />
            thinking…
          </span>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {tab === 'log' && (
          <div>
            {state.communicationLog.length === 0 ? (
              <p className="text-slate-400 text-sm text-center py-8">No activity yet</p>
            ) : (
              state.communicationLog.map((entry, i) => (
                <LogEntry key={i} text={entry} />
              ))
            )}
            <div ref={logEndRef} />
          </div>
        )}

        {tab === 'thinking' && (
          <div
            ref={thinkRef}
            className="thinking-stream p-4 text-slate-700 h-full"
          >
            {state.thinkingText || (
              <span className="text-slate-400 text-sm">Thinking output will appear here…</span>
            )}
            {state.thinkingActive && (
              <span className="inline-block w-1.5 h-4 bg-purple-400 ml-0.5 animate-pulse" />
            )}
          </div>
        )}

        {tab === 'specs' && (
          <div className="p-4">
            {state.specs ? (
              <pre className="text-xs text-slate-700 whitespace-pre-wrap font-mono leading-relaxed">{state.specs}</pre>
            ) : (
              <p className="text-slate-400 text-sm text-center py-8">Specifications will appear here</p>
            )}
          </div>
        )}

        {tab === 'report' && (
          <div className="p-4">
            {state.finalReport ? (
              <pre className="text-xs text-slate-700 whitespace-pre-wrap font-mono leading-relaxed">{state.finalReport}</pre>
            ) : (
              <p className="text-slate-400 text-sm text-center py-8">Final report will appear here</p>
            )}
            {state.integrationBugs?.length > 0 && (
              <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                <p className="text-xs font-semibold text-amber-700 mb-2">Integration issues:</p>
                <ul className="list-disc list-inside space-y-1">
                  {state.integrationBugs.map((b, i) => (
                    <li key={i} className="text-xs text-amber-600">{b}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
