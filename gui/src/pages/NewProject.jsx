import { useEffect, useRef, useState } from 'react'
import { useApp } from '../store.jsx'
import { api } from '../api'
import { Upload, Play, ChevronDown } from 'lucide-react'

function DropZone({ onFile }) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)
  const [fileName, setFileName] = useState(null)

  const handleFile = (file) => {
    if (!file) return
    setFileName(file.name)
    const reader = new FileReader()
    reader.onload = (e) => onFile(e.target.result)
    reader.readAsText(file)
  }

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => { e.preventDefault(); setDragging(false); handleFile(e.dataTransfer.files[0]) }}
      className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer
        ${dragging ? 'border-blue-400 bg-blue-50' : 'border-slate-300 hover:border-slate-400 bg-white'}`}
      onClick={() => inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".txt"
        className="hidden"
        onChange={(e) => handleFile(e.target.files[0])}
      />
      <Upload size={28} className="mx-auto text-slate-400 mb-3" />
      {fileName ? (
        <p className="text-sm font-medium text-blue-600">{fileName}</p>
      ) : (
        <>
          <p className="text-sm font-medium text-slate-600">Drop your requirements file here</p>
          <p className="text-xs text-slate-400 mt-1">or click to browse (.txt)</p>
        </>
      )}
    </div>
  )
}

function Select({ label, value, onChange, options }) {
  return (
    <div className="space-y-1.5">
      <label className="text-sm font-medium text-slate-700">{label}</label>
      <div className="relative">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full appearance-none bg-white border border-slate-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 pr-8"
        >
          {options.map((o) => (
            <option key={o} value={o}>{o}</option>
          ))}
        </select>
        <ChevronDown size={14} className="absolute right-3 top-3 text-slate-400 pointer-events-none" />
      </div>
    </div>
  )
}

function NumberInput({ label, value, onChange, min, max, step }) {
  return (
    <div className="space-y-1.5">
      <label className="text-sm font-medium text-slate-700">{label}</label>
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        min={min}
        max={max}
        step={step}
        className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
      />
    </div>
  )
}

function Checkbox({ label, desc, checked, onChange }) {
  return (
    <label className="flex items-start gap-3 cursor-pointer group">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-0.5 w-4 h-4 rounded accent-blue-600"
      />
      <div>
        <p className="text-sm font-medium text-slate-700 group-hover:text-slate-900">{label}</p>
        {desc && <p className="text-xs text-slate-400 mt-0.5">{desc}</p>}
      </div>
    </label>
  )
}

export default function NewProject() {
  const { dispatch } = useApp()
  const [requirements, setRequirements] = useState('')
  const [providers, setProviders] = useState(['ollama'])
  const [provider, setProvider] = useState('ollama')
  const [rpm, setRpm] = useState(0)
  const [timeout, setTimeout_] = useState(120)
  const [thinking, setThinking] = useState(false)
  const [askApproval, setAskApproval] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.getProviders().then((p) => setProviders([...p].sort())).catch(() => {})
  }, [])

  const launch = async () => {
    if (!requirements.trim()) { setError('Please provide project requirements.'); return }
    setError(null)
    setLoading(true)
    try {
      const { thread_id } = await api.startProject({
        requirements, provider, rpm, timeout, thinking, ask_approval: askApproval,
      })
      dispatch({ type: 'SET_THREAD', threadId: thread_id })
    } catch (e) {
      setError(e.message)
      setLoading(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto px-6 py-10 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Start New Project</h1>
        <p className="text-slate-500 text-sm mt-1">Upload or paste your requirements to start a new run.</p>
      </div>

      {/* Requirements */}
      <div className="space-y-3">
        <DropZone onFile={setRequirements} />
        <div className="relative">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-slate-200" />
          </div>
          <div className="relative flex justify-center">
            <span className="bg-slate-100 px-3 text-xs text-slate-400">or paste</span>
          </div>
        </div>
        <textarea
          value={requirements}
          onChange={(e) => setRequirements(e.target.value)}
          rows={5}
          placeholder="Paste project requirements here…"
          className="w-full bg-white border border-slate-300 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 resize-none"
        />
      </div>

      {/* Settings */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-5">
        <h2 className="text-sm font-semibold text-slate-700">Settings</h2>
        <div className="grid grid-cols-2 gap-4">
          <Select label="LLM Provider" value={provider} onChange={setProvider} options={providers} />
          <NumberInput label="Rate Limit (RPM)" value={rpm} onChange={setRpm} min={0} step={5} />
          <NumberInput label="LLM Timeout (s)" value={timeout} onChange={setTimeout_} min={30} step={10} />
        </div>
        <div className="space-y-3 pt-1">
          <Checkbox
            label="Enable thinking stream"
            desc="Stream raw LLM reasoning tokens (supported models only)"
            checked={thinking}
            onChange={setThinking}
          />
          <Checkbox
            label="Ask for approval"
            desc="Pause after planning to review and approve spec / task plan"
            checked={askApproval}
            onChange={setAskApproval}
          />
        </div>
      </div>

      {error && (
        <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-2">
          {error}
        </p>
      )}

      <button
        onClick={launch}
        disabled={loading || !requirements.trim()}
        className="w-full flex items-center justify-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-xl font-semibold text-sm hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        <Play size={16} />
        {loading ? 'Starting…' : 'Launch Project'}
      </button>
    </div>
  )
}
