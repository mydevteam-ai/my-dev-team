import { useEffect, useRef } from 'react'
import { useApp } from '../store.jsx'
import { Activity } from 'lucide-react'
import Markdown from './Markdown'

export default function ChatWindow() {
  const { state } = useApp()
  const endRef = useRef(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [state.activityFeed.length, state.thinkingBuffer])

  return (
    <div className="bg-white border border-slate-200 rounded-xl flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex border-b border-slate-200 px-2 shrink-0">
        <div className="flex items-center gap-1.5 px-3 py-2 text-sm border-b-2 border-blue-500 text-blue-600 font-medium">
          <Activity size={13} />
          Activity
        </div>
        {state.thinkingActive && (
          <span className="ml-auto self-center mr-2 text-xs text-purple-500 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-purple-400 pulse-dot" />
            thinking…
          </span>
        )}
      </div>

      {/* Feed */}
      <div className="flex-1 overflow-y-auto p-3 font-mono text-xs leading-relaxed space-y-1">
        {state.activityFeed.length === 0 && !state.thinkingBuffer && (
          <p className="text-slate-400 text-center py-8 font-sans text-sm">No activity yet</p>
        )}

        {state.activityFeed.map((entry, i) => (
          entry.type === 'log'
            ? <div key={i} className="border-l-2 border-blue-300 pl-2 [&_*]:font-bold [&_h1]:text-sm [&_h2]:text-sm [&_h3]:text-xs">
                <Markdown>{entry.text}</Markdown>
              </div>
            : <p key={i} className="text-slate-400 whitespace-pre-wrap font-mono text-xs">{entry.text}</p>
        ))}

        {/* Live thinking buffer (not yet flushed) */}
        {state.thinkingBuffer && (
          <p className="text-slate-500 whitespace-pre-wrap">
            {state.thinkingBuffer}
            {state.thinkingActive && (
              <span className="inline-block w-1.5 h-3.5 bg-purple-400 ml-0.5 animate-pulse" />
            )}
          </p>
        )}

        <div ref={endRef} />
      </div>
    </div>
  )
}
