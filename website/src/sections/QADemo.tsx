import { useState } from 'react'
import { ask, type AnswerMode, type AskResponse } from '@/lib/api'

const EXAMPLES = ['为什么赵眜墓里会出现“文帝行玺”？', '丝缕玉衣为什么不用金缕？', '第一次来最值得看的三件文物？']
const MODES: { value: AnswerMode; label: string }[] = [{ value: 'auto', label: '自动' }, { value: 'brief', label: '1分钟' }, { value: 'deep', label: '深入' }]

export function QADemo() {
  const [question, setQuestion] = useState(EXAMPLES[0]); const [mode, setMode] = useState<AnswerMode>('auto')
  const [result, setResult] = useState<AskResponse | null>(null); const [error, setError] = useState(''); const [loading, setLoading] = useState(false); const [proofOpen, setProofOpen] = useState(false)
  const submit = async (value = question) => { if (!value.trim() || loading) return; setQuestion(value); setLoading(true); setError(''); setResult(null); try { setResult(await ask(value.trim(), mode)) } catch (err) { setError(err instanceof Error ? err.message : '服务暂时不可用，请稍后重试。') } finally { setLoading(false) } }
  return <section id="qa" className="museum-section scroll-mt-20 qa-section"><div className="museum-heading"><span>叁</span><div><p>有据可查的回答</p><h2>AI 问南越</h2></div></div>
    <div className="qa-shell"><div className="qa-prompt"><p>问问两千年前的南越</p><textarea value={question} onChange={(event) => setQuestion(event.target.value)} maxLength={500} placeholder="例如：为什么赵眜墓里会出现“文帝行玺”？" aria-label="输入关于南越的问题" />
      <div className="qa-controls"><div role="group" aria-label="回答长度">{MODES.map((item) => <button key={item.value} className={mode === item.value ? 'selected' : ''} onClick={() => setMode(item.value)}>{item.label}</button>)}</div><button className="ink-button" disabled={loading || !question.trim()} onClick={() => submit()}>{loading ? '正在查找史料…' : '提问'}</button></div>
      <div className="example-questions"><span>也可以问：</span>{EXAMPLES.map((example) => <button key={example} onClick={() => submit(example)}>{example}</button>)}</div></div>
      <div className="answer-panel" aria-live="polite">{loading && <div className="answer-state"><span className="seal-stamp" aria-hidden>印</span><span>正在沿着史料与关系寻找答案…</span></div>}{error && <p className="answer-error">{error}</p>}{result && <><p className="answer-label">{result.insufficient_evidence ? '资料边界' : '南越数字博物志'}</p><div className="answer-text">{result.answer.split('\n').map((line, index) => <p key={index}>{line}</p>)}</div>{result.warning && <p className="answer-warning">{result.warning}</p>}
        <div className="answer-footer"><span>{result.generation_mode} · {Math.round(result.elapsed_ms)}ms</span><button className="trace-seal" onClick={() => setProofOpen(!proofOpen)} aria-expanded={proofOpen}>可溯</button></div>
        {proofOpen && <div className="proof"><h3>回答依据</h3><p>{result.route_reason}</p>{result.citations.map((citation) => <article key={citation.doc_id}><b>{citation.doc_id} · {citation.title}</b><blockquote>{citation.evidence}</blockquote><a href={citation.source_url} target="_blank" rel="noreferrer">{citation.source_name} · 查看原始史料 ↗</a></article>)}{result.web_sources.map((source) => <article key={source.url}><b>{source.title}</b><a href={source.url} target="_blank" rel="noreferrer">联网补充来源 ↗</a></article>)}{!result.citations.length && !result.web_sources.length && <p>本次未生成可引用的回答，系统已遵循资料边界。</p>}</div>}
        {result.suggested_questions.length > 0 && <div className="suggestions">{result.suggested_questions.map((item) => <button key={item} onClick={() => submit(item)}>{item}</button>)}</div>}</>}</div></div></section>
}
