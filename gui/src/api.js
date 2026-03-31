/**
 * API client for the Flask backend.
 */

const BASE = '/api'

async function req(method, path, body) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  }
  if (body !== undefined) opts.body = JSON.stringify(body)
  const res = await fetch(`${BASE}${path}`, opts)
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`)
  return data
}

export const api = {
  getProviders: () => req('GET', '/providers'),
  getThreads: () => req('GET', '/threads'),
  startProject: (payload) => req('POST', '/projects', payload),
  resumeProject: (threadId, payload) => req('POST', `/projects/${threadId}/resume`, payload),
  submitHitl: (threadId, payload) => req('POST', `/projects/${threadId}/hitl`, payload),
  getHistory: (threadId) => req('GET', `/projects/${threadId}/history`),
  getState: (threadId) => req('GET', `/projects/${threadId}/state`),
}

/**
 * Open a Server-Sent Events stream for a project.
 * @param {string} threadId
 * @param {number} fromIndex  resume from this event index (for reconnect)
 * @param {(event: object) => void} onEvent
 * @returns {{ close: () => void }}
 */
export function openStream(threadId, fromIndex, onEvent) {
  const url = `${BASE}/projects/${threadId}/stream?from=${fromIndex}`
  const es = new EventSource(url)

  es.onmessage = (e) => {
    try {
      const event = JSON.parse(e.data)
      onEvent(event)
    } catch {
      // ignore parse errors
    }
  }

  es.onerror = () => {
    es.close()
  }

  return { close: () => es.close() }
}
