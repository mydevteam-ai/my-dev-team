import ReactMarkdown from 'react-markdown'

export default function Markdown({ children, className = '' }) {
  return (
    <div className={`md-prose text-sm text-slate-700 ${className}`}>
      <ReactMarkdown>{children || ''}</ReactMarkdown>
    </div>
  )
}
