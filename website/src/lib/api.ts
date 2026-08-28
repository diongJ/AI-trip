export type AnswerMode = 'auto' | 'brief' | 'deep'

export interface Citation {
  doc_id: string
  title: string
  source_name: string
  source_url: string
  evidence: string
}

export interface WebSource { title: string; url: string; accessed_at: string }

export interface AskResponse {
  answer: string
  citations: Citation[]
  web_sources: WebSource[]
  route_reason: string
  used_tools: string[]
  insufficient_evidence: boolean
  response_status: string
  suggested_questions: string[]
  generation_mode: string
  warning: string | null
  elapsed_ms: number
}

export interface Entity { id: string; name: string; type: string; aliases: string[] }
export interface GraphRelation {
  source: Entity
  relation: string
  target: Entity
  direction: 'outgoing' | 'incoming'
  document_id: string
  evidence: string
}

const API_BASE = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ?? ''

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(payload?.detail ?? '服务暂时不可用，请稍后重试。')
  }
  return response.json() as Promise<T>
}

export function ask(question: string, answerMode: AnswerMode): Promise<AskResponse> {
  return request('/api/ask', { method: 'POST', body: JSON.stringify({ question, answerMode }) })
}

export function findEntities(q = '', type?: string): Promise<{ entities: Entity[] }> {
  const params = new URLSearchParams({ q, limit: '24' })
  if (type) params.set('type', type)
  return request(`/api/entities?${params}`)
}

export function getNeighbors(name: string): Promise<{ entity: Entity; neighbors: GraphRelation[] }> {
  return request(`/api/entities/${encodeURIComponent(name)}/neighbors`)
}
