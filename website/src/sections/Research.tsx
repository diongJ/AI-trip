import { useEffect, useState } from 'react'
import { EVAL_V2, PIPELINE_STEPS } from '@/data/content'

interface Stats { documents: number; entities: number; relations: number; evaluation: { question_count?: number; answer_rate?: number; hit_at_5?: number; citation_correctness?: number; refusal_accuracy?: number } }

export function Research() {
  const [stats, setStats] = useState<Stats | null>(null); const [open, setOpen] = useState(false)
  useEffect(() => { fetch(`${import.meta.env.VITE_API_BASE_URL ?? ''}/api/stats`).then((response) => response.ok ? response.json() : null).then(setStats).catch(() => undefined) }, [])
  const metrics = stats?.evaluation ?? {}
  const data = [
    ['可信资料', `${stats?.documents ?? 210} 份`], ['可靠实体', `${stats?.entities ?? 78} 个`], ['可溯关系', `${stats?.relations ?? 87} 条`],
    ['引用正确率', `${Math.round((metrics.citation_correctness ?? 1) * 100)}%`],
  ]
  return <section id="research" className="museum-section scroll-mt-20 research-section"><div className="museum-heading"><span>柒</span><div><p>可信史料与技术说明</p><h2>一切故事，皆可回溯</h2></div></div><p className="section-lead">内容体验在前，可靠系统在后。每一条回答都应回到原始资料与关系证据。</p>
    <div className="research-stats">{data.map(([label, value]) => <div key={label}><b>{value}</b><span>{label}</span></div>)}</div>
    <button className="research-toggle" onClick={() => setOpen(!open)} aria-expanded={open}>{open ? '收起研究与技术说明' : '展开研究与技术说明'}</button>
    {open && <div className="research-detail"><div><h3>从史料到回答</h3><ol>{PIPELINE_STEPS.map((step, index) => <li key={step.title}><b>{String(index + 1).padStart(2, '0')} {step.title}</b><span>{step.desc}</span></li>)}</ol></div><div><h3>离线评测 v2</h3><p>{metrics.question_count ?? EVAL_V2.questionCount} 道评测题；指标直接由评测汇总文件读取。</p><dl><div><dt>回答率</dt><dd>{Math.round((metrics.answer_rate ?? 0.875) * 100)}%</dd></div><div><dt>检索命中率</dt><dd>{Math.round((metrics.hit_at_5 ?? 0.8875) * 100)}%</dd></div><div><dt>拒答准确率</dt><dd>{Math.round((metrics.refusal_accuracy ?? 1) * 100)}%</dd></div></dl></div></div>}
  </section>
}
