/**
 * Global app state via React Context + useReducer.
 */
import { createContext, useContext, useReducer } from 'react'

const initialState = {
  // Navigation
  page: 'welcome',          // welcome | new-project | dashboard | resume | history

  // Active project
  threadId: null,
  running: false,
  eventIndex: 0,

  // Execution state (mirrors ProjectState fields)
  currentPhase: 'planning', // planning | development | integration | complete
  currentAgent: '',
  currentTask: '',
  currentTaskName: '',
  currentTaskIndex: 0,
  totalTasks: 0,
  revisionCount: 0,
  workspaceFiles: {},
  communicationLog: [],     // raw list - used only to detect new entries
  specs: '',
  finalReport: '',
  integrationBugs: [],
  pendingTasks: [],         // full task objects from architect
  completedTasks: [],
  failedTasks: [],
  aborted: false,
  error: null,

  // Interleaved activity feed: [{type: 'log'|'thinking', text: string}]
  activityFeed: [],
  // Current in-progress thinking buffer (not yet flushed to feed)
  thinkingBuffer: '',
  thinkingActive: false,

  // HITL
  hitlPending: false,
  hitlMode: null,           // clarification | approval_spec | approval_plan
  hitlQuestion: '',
  hitlSpecs: '',
  hitlTasks: [],
}

/** Flush pending thinking buffer into the feed and reset it. */
function flushThinking(feed, buffer) {
  if (buffer) feed.push({ type: 'thinking', text: buffer })
}

function reducer(state, action) {
  switch (action.type) {
    case 'NAVIGATE':
      return { ...state, page: action.page }

    case 'SET_THREAD':
      return { ...initialState, threadId: action.threadId, running: true, page: 'dashboard' }

    case 'EVENT': {
      const ev = action.event
      let next = { ...state, eventIndex: state.eventIndex + 1 }

      if (ev.type === '__done__') {
        return { ...next, running: false }
      }

      if (ev.type === 'thinking_token') {
        return {
          ...next,
          thinkingBuffer: state.thinkingBuffer + (ev.token || ''),
          thinkingActive: true,
        }
      }

      if (ev.type === 'hitl_request') {
        // Flush any pending thinking before pausing
        const feed = [...state.activityFeed]
        flushThinking(feed, state.thinkingBuffer)
        return {
          ...next,
          activityFeed: feed,
          thinkingBuffer: '',
          thinkingActive: false,
          hitlPending: true,
          hitlMode: ev.mode,
          hitlQuestion: ev.question || '',
          hitlSpecs: ev.specs || '',
          hitlTasks: ev.pending_tasks || [],
        }
      }

      if (ev.type === 'finish' || ev.type === 'error') {
        const fs = ev.state || {}
        const newLogs = fs.communication_log || []
        const feed = [...state.activityFeed]
        flushThinking(feed, state.thinkingBuffer)
        for (let i = state.communicationLog.length; i < newLogs.length; i++) {
          feed.push({ type: 'log', text: newLogs[i] })
        }
        return {
          ...next,
          running: false,
          thinkingBuffer: '',
          thinkingActive: false,
          hitlPending: false,
          activityFeed: feed,
          currentPhase: ev.type === 'finish' ? 'complete' : state.currentPhase,
          aborted: !!fs.abort_requested,
          error: fs.error_message || (ev.type === 'error' ? 'Execution failed' : null),
          communicationLog: newLogs,
          workspaceFiles: fs.workspace_files || state.workspaceFiles,
          specs: fs.specs || state.specs,
          finalReport: fs.final_report || state.finalReport,
          integrationBugs: fs.integration_bugs || state.integrationBugs,
          pendingTasks: fs.pending_tasks || state.pendingTasks,
          completedTasks: fs.completed_tasks || state.completedTasks,
          failedTasks: fs.failed_tasks || state.failedTasks,
        }
      }

      if (ev.type === 'step') {
        const fs = ev.full_state || {}
        const su = ev.state_update || {}
        const activeKey = Object.keys(su)[0] || ''
        const newLogs = fs.communication_log || []

        // Build updated feed: flush thinking, then append new log entries
        const feed = [...state.activityFeed]
        flushThinking(feed, state.thinkingBuffer)
        for (let i = state.communicationLog.length; i < newLogs.length; i++) {
          feed.push({ type: 'log', text: newLogs[i] })
        }

        return {
          ...next,
          thinkingBuffer: '',
          thinkingActive: false,
          hitlPending: false,
          activityFeed: feed,
          communicationLog: newLogs,
          currentPhase: fs.current_phase || state.currentPhase,
          currentAgent: activeKey,
          currentTask: fs.current_task || state.currentTask,
          currentTaskName: fs.current_task_name || state.currentTaskName,
          currentTaskIndex: fs.current_task_index ?? state.currentTaskIndex,
          totalTasks: (fs.pending_tasks || []).length || (fs.completed_tasks || []).length + (fs.failed_tasks || []).length || state.totalTasks,
          revisionCount: fs.revision_count ?? state.revisionCount,
          workspaceFiles: fs.workspace_files || state.workspaceFiles,
          specs: fs.specs || state.specs,
          finalReport: fs.final_report || state.finalReport,
          integrationBugs: fs.integration_bugs || state.integrationBugs,
          pendingTasks: fs.pending_tasks || state.pendingTasks,
          completedTasks: fs.completed_tasks || state.completedTasks,
          failedTasks: fs.failed_tasks || state.failedTasks,
        }
      }

      if (ev.type === 'start') {
        return { ...next, running: true, currentPhase: 'planning', thinkingBuffer: '', thinkingActive: false }
      }

      return next
    }

    case 'HITL_SUBMITTED':
      return { ...state, hitlPending: false, hitlMode: null }

    case 'RESET':
      return { ...initialState }

    default:
      return state
  }
}

const AppContext = createContext(null)

export function AppProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initialState)
  return <AppContext.Provider value={{ state, dispatch }}>{children}</AppContext.Provider>
}

export function useApp() {
  return useContext(AppContext)
}
