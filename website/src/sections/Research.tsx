import { useEffect, useState } from 'react'
import { EVAL_V2, PIPELINE_STEPS } from '@/data/content'
import { DotGrid } from '@/components/Patterns'

interface Stats { documents: number; entities: number; relations: number; evaluation: { question_count?: number; answer_rate?: number; hit_at_5?: number; citation_correctness?: number; refusal_accuracy?: number } }
const FLOW = [
  { key: 'source', no: '壹', title: '可信资料', text: '官方与审核资料' },
  { key: 'retrieve', no: '贰', title: 'KG / BM25', text: '关系与文本并行检索' },
  { key: 'agent', no: '叁', title: '证据约束 Agent', text: '规划、筛选与核验' },
  { key: 'llm', no: '肆', title: 'DeepSeek', text: '只负责组织语言' },
  { key: 'answer', no: '伍', title: '答案与引用', text: '同一证据链输出' },
]

export function Research() {
  const [stats, setStats] = useState<Stats | null>(null); const [open, setOpen] = useState(false)
  useEffect(() => { fetch(`${import.meta.env.VITE_API_BASE_URL ?? ''}/api/stats`).then((response) => response.ok ? response.json() : null).then(setStats).catch(() => undefined) }, [])
  const metrics = stats?.evaluation ?? {}
  const data = [['可信资料', `${stats?.documents ?? 220} 份`], ['可靠实体', `${stats?.entities ?? 78} 个`], ['可溯关系', `${stats?.relations ?? 87} 条`], ['引用正确率', `${Math.round((metrics.citation_correctness ?? 1) * 100)}%`]]
  return <section id="research" className="museum-section scroll-mt-20 research-section pattern-section"><DotGrid /><div className="museum-heading"><span>陆</span><div><p>可信史料与技术说明</p><h2>一切故事，皆可回溯</h2></div></div><p className="section-lead">内容体验在前，可靠系统在后。回答、引用与降级结果始终回到同一条证据链。</p>
    <div className="research-stats">{data.map(([label, value]) => <div key={label}><b>{value}</b><span>{label}</span></div>)}</div>
    <button className="research-toggle" onClick={() => setOpen(!open)} aria-expanded={open}>{open ? '收起研究与技术说明' : '展开研究与技术说明'}</button>
    {open && <div className="research-expanded">
      <div className="evidence-flow" aria-label="从可信资料到可溯回答的系统流程">{FLOW.map((item, index) => <div className={`flow-node flow-${item.key}`} key={item.key}><span>{item.no}</span><b>{item.title}</b><small>{item.text}</small>{index < FLOW.length - 1 && <i aria-hidden="true">→</i>}</div>)}</div>
      <div className="fallback-rails"><div><b>模型不可用</b><span>DeepSeek 超时或校验失败</span><i>→</i><strong>离线证据摘录</strong></div><div><b>图数据库不可用</b><span>Neo4j 未配置或连接失败</span><i>→</i><strong>本地 JSON 图谱</strong></div><p>生产环境暂不加载约 2GB 的 BGE 模型，以 BM25 / RRF 保持稳定与轻量；任何生成内容都不能脱离检索证据。</p></div>
      <div className="research-detail"><div><h3>从史料到回答</h3><ol>{PIPELINE_STEPS.map((step, index) => <li key={step.title}><b>{String(index + 1).padStart(2, '0')} {step.title}</b><span>{step.desc}</span></li>)}</ol></div><div><h3>离线评测 v2</h3><p>{metrics.question_count ?? EVAL_V2.questionCount} 道评测题；数据由评测汇总文件读取，不代表 DeepSeek 公网响应时间。</p><dl><div><dt>回答率</dt><dd>{Math.round((metrics.answer_rate ?? 0.875) * 100)}%</dd></div><div><dt>检索命中率</dt><dd>{Math.round((metrics.hit_at_5 ?? 0.8875) * 100)}%</dd></div><div><dt>拒答准确率</dt><dd>{Math.round((metrics.refusal_accuracy ?? 1) * 100)}%</dd></div></dl></div></div>
    </div>}
  </section>
}
