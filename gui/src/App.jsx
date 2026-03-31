import { useEffect, useRef } from 'react'
import { AppProvider, useApp } from './store.jsx'
import { openStream } from './api'
import Sidebar from './components/Sidebar'
import Welcome from './pages/Welcome'
import NewProject from './pages/NewProject'
import Dashboard from './pages/Dashboard'
import ResumeProject from './pages/ResumeProject'
import History from './pages/History'

function Inner() {
  const { state, dispatch } = useApp()
  const streamRef = useRef(null)

  // Open/close SSE stream when threadId + running state changes
  useEffect(() => {
    if (!state.threadId || !state.running) {
      streamRef.current?.close()
      streamRef.current = null
      return
    }

    // Already streaming
    if (streamRef.current) return

    streamRef.current = openStream(state.threadId, state.eventIndex, (event) => {
      dispatch({ type: 'EVENT', event })
      if (event.type === '__done__' || event.type === 'finish' || event.type === 'error') {
        streamRef.current?.close()
        streamRef.current = null
      }
    })

    return () => {
      streamRef.current?.close()
      streamRef.current = null
    }
  }, [state.threadId, state.running]) // eslint-disable-line react-hooks/exhaustive-deps

  const pages = {
    welcome: <Welcome />,
    'new-project': <NewProject />,
    dashboard: <Dashboard />,
    resume: <ResumeProject />,
    history: <History />,
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto bg-slate-100">
        {pages[state.page] || <Welcome />}
      </main>
    </div>
  )
}

export default function App() {
  return (
    <AppProvider>
      <Inner />
    </AppProvider>
  )
}
