import { useCallback, useEffect, useState } from 'react'
import { findEntities, getExplorationPaths, getNeighbors, type Entity, type ExplorationPath, type GraphRelation } from '@/lib/api'

const TYPES = [
  { label: '人物', value: 'Person' }, { label: '文物', value: 'Relic' },
  { label: '墓葬', value: 'Tomb' }, { label: '地点', value: 'TombChamber' }, { label: '政权', value: 'State' },
]
const STARTERS = ['赵眜', '文帝行玺', '丝缕玉衣', '南越文王墓']
const TYPE_LABELS: Record<string, string> = {
  Person: '人物', Relic: '文物', Tomb: '墓葬', TombChamber: '墓室', State: '政权', Dynasty: '时代',
  Culture: '文化', HistoricalEvent: '历史事件', Material: '材质', Pattern: '纹饰',
}

interface Props { requestedEntity?: string; onConsumed?: () => void; onAsk: (question: string) => void }

export function GraphExplorer({ requestedEntity, onConsumed, onAsk }: Props) {
  const [paths, setPaths] = useState<ExplorationPath[]>([])
  const [pathIndex, setPathIndex] = useState(0); const [stepIndex, setStepIndex] = useState(0)
  const [query, setQuery] = useState(''); const [type, setType] = useState(''); const [entities, setEntities] = useState<Entity[]>([])
  const [selected, setSelected] = useState<Entity | null>(null); const [relations, setRelations] = useState<GraphRelation[]>([])
  const [trail, setTrail] = useState<Entity[]>([]); const [message, setMessage] = useState('请选择一条线索，关系会在这里展开。')
  const [freeOpen, setFreeOpen] = useState(false)

  const search = useCallback(async (value = query, selectedType = type) => {
    setQuery(value)
    try { const result = await findEntities(value, selectedType || undefined); setEntities(result.entities); if (!result.entities.length) setMessage('当前资料中没有找到匹配实体。') }
    catch { setMessage('图谱服务暂时不可用，请稍后重试。') }
  }, [query, type])

  const choose = useCallback(async (entity: Entity | string, fromTrail = false) => {
    const name = typeof entity === 'string' ? entity : entity.name
    setMessage('正在寻找相关证据…')
    try {
      const result = await getNeighbors(name); setSelected(result.entity); setRelations(result.neighbors)
      const existing = trail.findIndex((item) => item.name === result.entity.name)
      setTrail(existing >= 0 ? trail.slice(0, existing + 1) : [...trail, result.entity])
      setMessage(result.neighbors.length ? (existing >= 0 && !fromTrail ? '已回到走过的线索，路径不会重复成环。' : '') : '该实体暂未找到可展示的一跳关系。')
    } catch { setRelations([]); setMessage('尚未找到这条线索，可以从推荐实体重新开始。') }
  }, [trail])

  useEffect(() => {
    void Promise.all([getExplorationPaths(), findEntities()]).then(([pathResult, entityResult]) => { setPaths(pathResult.paths); setEntities(entityResult.entities) }).catch(() => setMessage('循证路径暂时不可用，请稍后重试。'))
  }, [])
  useEffect(() => { if (!query.trim()) return; const timer = window.setTimeout(() => { void search(query, type) }, 300); return () => window.clearTimeout(timer) }, [query, type, search])
  useEffect(() => {
    if (!requestedEntity) return
    const timer = window.setTimeout(() => {
      setFreeOpen(true); void choose(requestedEntity); onConsumed?.()
      document.getElementById('relations')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 0)
    return () => window.clearTimeout(timer)
  }, [requestedEntity, onConsumed, choose])

  const path = paths[pathIndex]; const step = path?.steps[stepIndex]
  const otherEntity = (relation: GraphRelation) => relation.source.name === selected?.name ? relation.target : relation.source

  return <section id="relations" className="museum-section scroll-mt-20 relations-section">
    <div className="museum-heading"><span>伍</span><div><p>每一步都有出处</p><h2>循证探秘</h2></div></div>
    <p className="section-lead">选择一条人工核验的故事线，像研究者一样从证据走向结论；关系只说明资料明确支持的内容。</p>
    <div className="path-tabs" role="tablist" aria-label="循证探索路径">{paths.map((item, index) => <button key={item.id} role="tab" aria-selected={pathIndex === index} className={pathIndex === index ? 'selected' : ''} onClick={() => { setPathIndex(index); setStepIndex(0) }}><small>路径 {index + 1}</small><b>{item.title}</b></button>)}</div>
    {path && step ? <div className="evidence-journey">
      <header><div><span>{String(stepIndex + 1).padStart(2, '0')} / {String(path.steps.length).padStart(2, '0')}</span><h3>{step.question}</h3><p>{stepIndex === 0 ? path.intro : step.bridge}</p></div><ol aria-label="路径进度">{path.steps.map((item, index) => <li key={item.id} className={index <= stepIndex ? 'active' : ''}><button onClick={() => setStepIndex(index)} aria-label={`前往第 ${index + 1} 条证据`}>{index + 1}</button></li>)}</ol></header>
      <div className="evidence-relation" aria-label={`${step.source_entity}${step.relation_label}${step.target_entity}`}><strong>{step.source_entity}</strong><span><i />{step.relation_label}<i /></span><strong>{step.target_entity}</strong></div>
      <div className="evidence-copy"><div><small>阶段结论</small><p>{step.conclusion}</p></div><div><small>原文证据</small><blockquote>“{step.evidence}”</blockquote><a href={step.citation.source_url} target="_blank" rel="noreferrer">{step.citation.doc_id} · {step.citation.source_name} · 查看原始资料 ↗</a></div></div>
      {stepIndex === path.steps.length - 1 && <div className="journey-conclusion"><small>本路径结论</small><p>{path.conclusion}</p></div>}
      <footer><button disabled={stepIndex === 0} onClick={() => setStepIndex((value) => Math.max(0, value - 1))}>上一条证据</button><button className="ask-evidence" onClick={() => onAsk(step.ask_prompt)}>向 AI 追问</button><button disabled={stepIndex === path.steps.length - 1} onClick={() => setStepIndex((value) => Math.min(path.steps.length - 1, value + 1))}>下一条证据</button></footer>
    </div> : <p className="answer-state">正在核对策展路径…</p>}
    <div className="free-explorer"><button className="free-toggle" onClick={() => setFreeOpen(!freeOpen)} aria-expanded={freeOpen}>{freeOpen ? '收起自由实体探索' : '自由探索更多人物、文物与墓葬'}</button>{freeOpen && <div className="free-panel">
      <p>自由探索展示图谱中的一跳事实关系；遇到走过的实体会回到原节点，不会形成循环。</p>
      <div className="relation-tools"><input value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => event.key === 'Enter' && void search()} placeholder="搜索人物、文物、墓葬…" aria-label="搜索实体" /><button onClick={() => void search()} className="paper-button">搜索</button><div>{TYPES.map((item) => <button key={item.value} className={type === item.value ? 'selected' : ''} onClick={() => { const next = type === item.value ? '' : item.value; setType(next); void search(query, next) }}>{item.label}</button>)}</div></div>
      <div className="entity-chips">{(entities.length ? entities : STARTERS.map((name) => ({ id: name, name, type: '', aliases: [] }))).slice(0, 12).map((entity) => <button className={selected?.name === entity.name ? 'selected' : ''} key={entity.id} onClick={() => void choose(entity)}>{entity.name}{entity.type && <small>{TYPE_LABELS[entity.type] ?? entity.type}</small>}</button>)}</div>
      {trail.length > 0 && <nav className="entity-trail" aria-label="探索路径"><span>已走线索</span>{trail.map((entity, index) => <span key={`${entity.id}-${index}`}><button onClick={() => void choose(entity, true)}>{entity.name}</button>{index < trail.length - 1 && <i>→</i>}</span>)}{trail.length > 1 && <button className="trail-back" onClick={() => void choose(trail[trail.length - 2], true)}>返回上一步</button>}</nav>}
      <div className="relation-stage">{selected && <div className="relation-core"><span>{TYPE_LABELS[selected.type] ?? selected.type}</span><b>{selected.name}</b><p>从这里出发</p></div>}<div className="relation-list">{relations.map((relation, index) => { const other = otherEntity(relation); return <article key={`${relation.document_id}-${index}`}><p><span>{selected?.name} </span><b>{relation.relation_label}</b><button onClick={() => void choose(other)}> {other.name}</button></p><blockquote>{relation.evidence}</blockquote>{relation.citation ? <a href={relation.citation.source_url} target="_blank" rel="noreferrer">{relation.document_id} · {relation.citation.source_name} ↗</a> : <small>{relation.document_id}</small>}</article> })}{message && <p className="answer-state">{message}</p>}</div></div>
    </div>}</div>
  </section>
}
