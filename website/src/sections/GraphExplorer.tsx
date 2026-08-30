import { useEffect, useState } from 'react'
import { findEntities, getNeighbors, type Entity, type GraphRelation } from '@/lib/api'

const TYPES = [
  { label: '人物', value: 'Person' },
  { label: '文物', value: 'Relic' },
  { label: '墓葬', value: 'Tomb' },
  { label: '地点', value: 'TombChamber' },
  { label: '政权', value: 'State' },
]
const STARTERS = ['赵眜', '文帝行玺', '丝缕玉衣', '南越文王墓']

export function GraphExplorer({ requestedEntity, onConsumed }: { requestedEntity?: string; onConsumed?: () => void }) {
  const [query, setQuery] = useState(''); const [type, setType] = useState(''); const [entities, setEntities] = useState<Entity[]>([]); const [selected, setSelected] = useState<Entity | null>(null); const [relations, setRelations] = useState<GraphRelation[]>([]); const [message, setMessage] = useState('请选择一条线索，关系会在这里展开。')
  const search = async (value = query, selectedType = type) => { setQuery(value); try { const result = await findEntities(value, selectedType || undefined); setEntities(result.entities); if (!result.entities.length) setMessage('当前资料中没有找到匹配实体。') } catch { setMessage('图谱服务暂时不可用，请稍后重试。') } }
  const choose = async (entity: Entity | string) => { const name = typeof entity === 'string' ? entity : entity.name; setMessage('正在寻找相关证据…'); try { const result = await getNeighbors(name); setSelected(result.entity); setRelations(result.neighbors); setMessage(result.neighbors.length ? '' : '该实体暂未找到可展示的一跳关系。') } catch { setRelations([]); setMessage('尚未找到这条线索，可以从下方推荐实体开始。') } }
  useEffect(() => {
    const timer = window.setTimeout(() => {
      void findEntities().then((result) => setEntities(result.entities)).catch(() => setMessage('图谱服务暂时不可用，请稍后重试。'))
    }, 0)
    return () => window.clearTimeout(timer)
  }, [])
  useEffect(() => {
    if (!query.trim()) return
    const timer = window.setTimeout(() => {
      void findEntities(query, type || undefined)
        .then((result) => {
          setEntities(result.entities)
          if (!result.entities.length) setMessage('当前资料中没有找到匹配实体。')
        })
        .catch(() => setMessage('图谱服务暂时不可用，请稍后重试。'))
    }, 300)
    return () => window.clearTimeout(timer)
  }, [query, type])
  useEffect(() => {
    if (!requestedEntity) return
    const timer = window.setTimeout(() => {
      void getNeighbors(requestedEntity).then((result) => {
        setSelected(result.entity); setRelations(result.neighbors); setMessage(result.neighbors.length ? '' : '该实体暂未找到可展示的一跳关系。')
      }).catch(() => { setRelations([]); setMessage('尚未找到这条线索，可以从下方推荐实体开始。') })
    }, 0)
    onConsumed?.(); document.getElementById('relations')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    return () => window.clearTimeout(timer)
  }, [onConsumed, requestedEntity])
  return <section id="relations" className="museum-section scroll-mt-20 relations-section"><div className="museum-heading"><span>伍</span><div><p>知识不止是一张图</p><h2>关系探秘</h2></div></div><p className="section-lead">从一个人、一件文物或一座墓开始，沿着可靠证据继续追问。</p>
    <div className="relation-tools"><input value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => event.key === 'Enter' && void search()} placeholder="搜索人物、文物、墓葬…" aria-label="搜索实体" /><button onClick={() => void search()} className="paper-button">搜索</button><div>{TYPES.map((item) => <button key={item.value} className={type === item.value ? 'selected' : ''} onClick={() => { const next = type === item.value ? '' : item.value; setType(next); void search(query, next) }}>{item.label}</button>)}</div></div>
    <div className="entity-chips">{(entities.length ? entities : STARTERS.map((name) => ({ id: name, name, type: '', aliases: [] }))).slice(0, 12).map((entity) => <button className={selected?.name === entity.name ? 'selected' : ''} key={entity.id} onClick={() => void choose(entity)}>{entity.name}{entity.type && <small>{entity.type}</small>}</button>)}</div>
    <div className="relation-stage">{selected && <div className="relation-core"><span>{selected.type}</span><b>{selected.name}</b><p>从这里出发</p></div>}<div className="relation-list">{relations.map((relation, index) => { const other = relation.source.name === selected?.name ? relation.target : relation.source; return <article key={`${relation.document_id}-${index}`}><p><button onClick={() => void choose(other)}>{other.name}</button><span> {relation.relation} </span></p><blockquote>{relation.evidence}</blockquote><small>{relation.document_id}</small></article> })}{message && <p className="answer-state">{message}</p>}</div></div></section>
}
