import { useState } from 'react'
import { Sparkles, X, Send, Bot, User as UserIcon, Loader2, BarChart2 } from 'lucide-react'
import api, { AIQueryResponse } from '../lib/api'
import { useAuth } from '../context/AuthContext'

interface Message {
  id: string
  sender: 'user' | 'ai'
  text: string
  response?: AIQueryResponse
  timestamp: string
}

export default function AIQueryDrawer({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const { activeBusiness } = useAuth()
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      sender: 'ai',
      text: 'Hello! I am your AI Commerce Intelligence Assistant. Ask me anything about your revenue, contribution margins, MER & CAC, cohorts, or SKU profitability!',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ])

  if (!isOpen) return null

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim() || !activeBusiness || loading) return

    const userQuery = query.trim()
    const userMsg: Message = {
      id: Date.now().toString(),
      sender: 'user',
      text: userQuery,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }

    setMessages((prev) => [...prev, userMsg])
    setQuery('')
    setLoading(true)

    try {
      const { data } = await api.post<AIQueryResponse>(`/analytics/ai-query/${activeBusiness.id}`, { query: userQuery })
      const aiMsg: Message = {
        id: (Date.now() + 1).toString(),
        sender: 'ai',
        text: data.answer,
        response: data,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }
      setMessages((prev) => [...prev, aiMsg])
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          sender: 'ai',
          text: 'Sorry, I encountered an error querying your database metrics. Please check your data connection.',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  const suggestionPills = [
    'What is our Contribution Margin & MER/CAC?',
    'Show repeat purchase rate and LTV',
    'Which SKUs have low profit margins?',
    'What is our top sales channel by revenue?',
  ]

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-black/40 backdrop-blur-sm transition-opacity">
      <div className="absolute inset-y-0 right-0 flex max-w-full pl-10">
        <div className="w-screen max-w-lg bg-white shadow-2xl flex flex-col">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4 bg-slate-900 text-white">
            <div className="flex items-center space-x-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-brand-600 to-indigo-600 shadow">
                <Sparkles className="h-5 w-5 text-white" />
              </div>
              <div>
                <h2 className="text-base font-semibold text-white">AI Assistant (Moby)</h2>
                <p className="text-xs text-slate-400">Grounded in real database metrics</p>
              </div>
            </div>
            <button onClick={onClose} className="rounded-lg p-1 text-slate-400 hover:bg-slate-800 hover:text-white transition">
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Quick Suggestions */}
          <div className="border-b border-slate-100 bg-slate-50 px-4 py-2.5">
            <p className="text-[11px] font-medium text-slate-500 mb-1.5 uppercase tracking-wider">Suggested Queries</p>
            <div className="flex flex-wrap gap-1.5">
              {suggestionPills.map((pill, idx) => (
                <button
                  key={idx}
                  onClick={() => setQuery(pill)}
                  className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-slate-700 border border-slate-200 shadow-sm hover:border-brand-500 hover:text-brand-600 transition"
                >
                  {pill}
                </button>
              ))}
            </div>
          </div>

          {/* Chat Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50/50">
            {messages.map((m) => (
              <div key={m.id} className={`flex ${m.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`flex max-w-[85%] space-x-2.5 ${m.sender === 'user' ? 'flex-row-reverse space-x-reverse' : 'flex-row'}`}>
                  <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-medium ${m.sender === 'user' ? 'bg-brand-600 text-white' : 'bg-slate-900 text-white'}`}>
                    {m.sender === 'user' ? <UserIcon className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                  </div>

                  <div>
                    <div className={`rounded-2xl px-4 py-2.5 text-sm shadow-sm ${m.sender === 'user' ? 'bg-brand-600 text-white rounded-tr-none' : 'bg-white text-slate-800 border border-slate-200/80 rounded-tl-none'}`}>
                      <p className="whitespace-pre-wrap leading-relaxed">{m.text}</p>

                      {/* Structured Data Result Card */}
                      {m.response && m.response.data && m.response.data.length > 0 && (
                        <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-semibold text-slate-700 flex items-center gap-1">
                              <BarChart2 className="h-3.5 w-3.5 text-brand-600" />
                              Intent: {m.response.intent}
                            </span>
                            <span className="text-[10px] text-slate-500 uppercase font-mono">{m.response.chart_type}</span>
                          </div>

                          <div className="max-h-48 overflow-y-auto space-y-1 text-xs">
                            {m.response.data.slice(0, 5).map((row, rIdx) => (
                              <div key={rIdx} className="flex justify-between items-center py-1 border-b border-slate-200/60 last:border-0">
                                <span className="font-medium text-slate-700 truncate max-w-[140px]">
                                  {String(row.label || row.name || row.dimension || row.key || row.date || `Item ${rIdx + 1}`)}
                                </span>
                                <span className="font-semibold text-slate-900 tabular-nums">
                                  {String(row.value !== undefined ? row.value : row.metric_value !== undefined ? row.metric_value : row.actual_value !== undefined ? row.actual_value : row.contribution_margin !== undefined ? `₹${row.contribution_margin}` : '')}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                    <span className="mt-1 block text-[10px] text-slate-400 px-1">{m.timestamp}</span>
                  </div>
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex justify-start">
                <div className="flex items-center space-x-2 rounded-2xl bg-white border border-slate-200 px-4 py-3 text-sm text-slate-500 shadow-sm">
                  <Loader2 className="h-4 w-4 animate-spin text-brand-600" />
                  <span>Analyzing metrics from database...</span>
                </div>
              </div>
            )}
          </div>

          {/* Form Input */}
          <form onSubmit={handleSend} className="border-t border-slate-200 bg-white p-3">
            <div className="relative flex items-center">
              <input
                type="text"
                placeholder="Ask plain-English query about your data..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="input pr-12 text-sm shadow-sm"
              />
              <button
                type="submit"
                disabled={!query.trim() || loading}
                className="absolute right-1.5 flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-40 transition"
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
