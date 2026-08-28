import { useState } from 'react'
import { ask, type AskResponse } from '@/lib/api'

const INTENTS = [
  { key: 'story', mark: '◆', title: '听故事', prompt: '给我讲一个文帝行玺的小故事', desc: '把文物和历史讲成小故事' },
  { key: 'relic', mark: '✧', title: '认识文物', prompt: '丝缕玉衣是做什么用的？', desc: '用小朋友的话介绍文物' },
  { key: 'chat', mark: '越', title: '聊聊天', prompt: '你是谁呀？', desc: '和小越说说悄悄话' },
] as const

export function KidsQA() {
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<AskResponse | null>(null)
  const [error, setError] = useState('')
  const [proofOpen, setProofOpen] = useState(false)

  const submit = async (value: string) => {
    if (!value.trim() || loading) return
    setQuestion(value)
    setLoading(true)
    setError('')
    setResult(null)
    setProofOpen(false)
    try {
      setResult(await ask(value.trim(), 'auto', 'kids'))
    } catch (err) {
      setError(err instanceof Error ? err.message : '小越暂时走神了，请稍后再试。')
    } finally {
      setLoading(false)
    }
  }

  const answered = result && !result.insufficient_evidence && result.response_status !== 'chat'
  return (
    <section id="kids" className="museum-section scroll-mt-20 kids-section">
      <div className="museum-heading"><span>肆</span><div><p>小越的南越故事屋</p><h2>给小朋友的博物馆</h2></div></div>
      <p className="section-lead">你好呀小朋友！我是小越。所有回答都来自可靠资料，不联网、不编造——大人可以在下面看到依据。</p>
      <div className="kids-intents" role="list">
        {INTENTS.map((intent) => (
          <button key={intent.key} className="kids-intent-card" role="listitem" onClick={() => submit(intent.prompt)}>
            <span className="kids-mark" aria-hidden>{intent.mark}</span>
            <b>{intent.title}</b>
            <small>{intent.desc}</small>
            <em>{intent.prompt}</em>
          </button>
        ))}
      </div>
      <div className="kids-chat">
        <div className="kids-ask">
          <label htmlFor="kids-input">想和小越聊点什么？</label>
          <div className="kids-input-row">
            <input id="kids-input" value={question} onChange={(event) => setQuestion(event.target.value)} maxLength={200} placeholder="比如：给我讲一个文帝行玺的小故事" onKeyDown={(event) => { if (event.key === 'Enter') submit(question) }} aria-label="输入想对小越说的话" />
            <button className="ink-button" disabled={loading || !question.trim()} onClick={() => submit(question)}>{loading ? '小越在想…' : '问小越'}</button>
          </div>
        </div>
        <div className="kids-answer" aria-live="polite">
          {loading && <div className="kids-loading"><span className="seal-stamp" aria-hidden>越</span><span>小越正在翻阅博物馆的“藏宝图”…</span></div>}
          {error && <p className="answer-error">{error}</p>}
          {result && <div className="kids-reply">
            <p className="kids-avatar" aria-hidden>越</p>
            <div className="kids-reply-body">
              <p className="kids-name">小越</p>
              <div className="kids-text">{result.answer.split('\n').map((line, index) => <p key={index}>{line}</p>)}</div>
              {result.warning && <p className="answer-warning">{result.warning}</p>}
              <p className="kids-foot">{result.generation_mode} · {Math.round(result.elapsed_ms)}ms</p>
              {answered && result.citations.length > 0 && (
                <button className="kids-proof-toggle" onClick={() => setProofOpen(!proofOpen)} aria-expanded={proofOpen}>
                  {proofOpen ? '收起给大人的依据' : '给大人的依据（证据可查）'}
                </button>
              )}
              {proofOpen && result.citations.length > 0 && <div className="kids-proof">{result.citations.map((citation) => <article key={citation.doc_id}><b>{citation.doc_id} · {citation.title}</b><blockquote>{citation.evidence}</blockquote><a href={citation.source_url} target="_blank" rel="noreferrer">查看原始史料 ↗</a></article>)}</div>}
              {result.suggested_questions.length > 0 && <div className="suggestions">{result.suggested_questions.map((item) => <button key={item} onClick={() => submit(item)}>{item}</button>)}</div>}
            </div>
          </div>}
        </div>
      </div>
    </section>
  )
}
