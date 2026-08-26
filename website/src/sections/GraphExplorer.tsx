import { useMemo, useState } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Reveal } from '@/components/Reveal'
import { SectionHeading } from '@/sections/Stats'
import { GRAPH_NODES, GRAPH_EDGES, type NodeType } from '@/data/content'
import { Search, MapPin } from 'lucide-react'

const TYPE_COLORS: Record<NodeType, string> = {
  人物: '#9a3412',
  墓葬: '#26221c',
  文物: '#315c4d',
  地点: '#a16207',
  政权: '#5b5bd6',
}

const ALL_TYPES: NodeType[] = ['人物', '墓葬', '文物', '地点', '政权']

// 手工布局（viewBox 800x520），保证桌面/移动端一致可读
const POS: Record<string, { x: number; y: number }> = {
  zhaomo: { x: 400, y: 110 },
  tomb: { x: 400, y: 280 },
  seal: { x: 150, y: 200 },
  jadesuit: { x: 160, y: 400 },
  nanyue: { x: 640, y: 130 },
  xiangang: { x: 620, y: 410 },
  zhaotuo: { x: 560, y: 40 },
  jue: { x: 380, y: 460 },
}

/** 图谱探索演示区：真实数据驱动的 SVG 图谱，支持搜索、类型筛选、点选节点查看关系证据 */
export function GraphExplorer() {
  const [activeTypes, setActiveTypes] = useState<Set<NodeType>>(new Set(ALL_TYPES))
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<string | null>('tomb')

  const visibleNodes = useMemo(() => {
    const q = query.trim().toLowerCase()
    return GRAPH_NODES.filter((n) => {
      if (!activeTypes.has(n.type)) return false
      if (!q) return true
      return (
        n.label.toLowerCase().includes(q) ||
        (n.aliases ?? []).some((a) => a.toLowerCase().includes(q))
      )
    })
  }, [activeTypes, query])

  const visibleIds = new Set(visibleNodes.map((n) => n.id))
  const visibleEdges = GRAPH_EDGES.filter((e) => visibleIds.has(e.source) && visibleIds.has(e.target))

  const relatedEdges = selected
    ? GRAPH_EDGES.filter((e) => e.source === selected || e.target === selected)
    : []
  const selectedNode = GRAPH_NODES.find((n) => n.id === selected)

  const toggleType = (t: NodeType) => {
    setActiveTypes((prev) => {
      const next = new Set(prev)
      if (next.has(t)) next.delete(t)
      else next.add(t)
      return next
    })
  }

  const nodeById = (id: string) => GRAPH_NODES.find((n) => n.id === id)!

  const isDim = (id: string) =>
    selected != null &&
    id !== selected &&
    !relatedEdges.some((e) => e.source === id || e.target === id)

  return (
    <section id="graph" className="scroll-mt-20 border-y bg-secondary/40 py-16 sm:py-20">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <SectionHeading
          eyebrow="Graph Explorer"
          title="图谱探索演示"
          desc="以下为知识图谱 V1 的核心实体子集（完整图谱含 78 个实体、87 条关系）。点击节点查看关系与原文证据；支持名称/别名搜索与类型筛选。"
        />

        <Reveal className="mt-8">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="搜索实体或别名，如：赵眜、玉衣、文帝金印…"
                className="pl-9"
              />
            </div>
            <div className="flex flex-wrap gap-1.5">
              {ALL_TYPES.map((t) => (
                <button
                  key={t}
                  onClick={() => toggleType(t)}
                  className={`rounded-full border px-3 py-1 text-xs transition-all duration-200 ${
                    activeTypes.has(t)
                      ? 'border-primary bg-primary text-primary-foreground'
                      : 'bg-card text-muted-foreground hover:border-primary/50'
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
        </Reveal>

        <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-[1.4fr_1fr]">
          {/* 图谱画布 */}
          <Reveal>
            <Card className="overflow-hidden">
              <CardContent className="p-0">
                <svg viewBox="0 0 800 520" className="block w-full bg-grid-ink" role="img" aria-label="知识图谱示例">
                  {/* 边 */}
                  {visibleEdges.map((e, i) => {
                    const s = POS[e.source]
                    const t = POS[e.target]
                    const mx = (s.x + t.x) / 2
                    const my = (s.y + t.y) / 2
                    const active = selected != null && (e.source === selected || e.target === selected)
                    return (
                      <g key={i} opacity={selected && !active ? 0.15 : 1} style={{ transition: 'opacity .3s' }}>
                        <line x1={s.x} y1={s.y} x2={t.x} y2={t.y} stroke={active ? '#9a3412' : '#c9c2b2'} strokeWidth={active ? 1.8 : 1.2} />
                        <text x={mx} y={my - 4} textAnchor="middle" fontSize="11" fill={active ? '#9a3412' : '#8a8272'}>
                          {e.relation}
                        </text>
                      </g>
                    )
                  })}
                  {/* 节点 */}
                  {visibleNodes.map((n) => {
                    const p = POS[n.id]
                    const color = TYPE_COLORS[n.type]
                    const isSel = selected === n.id
                    return (
                      <g
                        key={n.id}
                        transform={`translate(${p.x}, ${p.y})`}
                        onClick={() => setSelected(isSel ? null : n.id)}
                        className="cursor-pointer"
                        opacity={isDim(n.id) ? 0.3 : 1}
                        style={{ transition: 'opacity .3s' }}
                      >
                        <circle
                          r={isSel ? 26 : 20}
                          fill={color}
                          fillOpacity={isSel ? 1 : 0.88}
                          stroke={isSel ? '#f7f4ec' : 'none'}
                          strokeWidth={3}
                        >
                          <animate attributeName="r" values={`${isSel ? 26 : 20};${isSel ? 28 : 22};${isSel ? 26 : 20}`} dur="4s" repeatCount="indefinite" />
                        </circle>
                        <text y={isSel ? 42 : 36} textAnchor="middle" fontSize="13" fontWeight={isSel ? 700 : 500} fill="#26221c">
                          {n.label}
                        </text>
                        <text y={isSel ? 56 : 50} textAnchor="middle" fontSize="10" fill="#8a8272">
                          {n.type}
                        </text>
                      </g>
                    )
                  })}
                </svg>
              </CardContent>
            </Card>
          </Reveal>

          {/* 关系详情面板 */}
          <Reveal delay={100}>
            <Card className="h-full">
              <CardContent className="p-5">
                {selectedNode ? (
                  <>
                    <div className="flex items-center gap-2">
                      <span className="inline-block h-3 w-3 rounded-full" style={{ background: TYPE_COLORS[selectedNode.type] }} />
                      <h3 className="font-serif-sc text-lg font-bold">{selectedNode.label}</h3>
                      <Badge variant="secondary" className="text-[11px]">{selectedNode.type}</Badge>
                    </div>
                    {selectedNode.aliases && (
                      <p className="mt-1 text-xs text-muted-foreground">
                        别名：{selectedNode.aliases.join('、')}
                      </p>
                    )}
                    <p className="mt-3 text-xs font-semibold">
                      一跳关系（{relatedEdges.length}）
                    </p>
                    <div className="mt-2 max-h-[320px] space-y-3 overflow-y-auto pr-1">
                      {relatedEdges.map((e, i) => {
                        const from = nodeById(e.source)
                        const to = nodeById(e.target)
                        return (
                          <div key={i} className="rounded-md border bg-secondary/40 p-3">
                            <p className="text-xs font-medium">
                              {from.label}
                              <span className="mx-1.5 text-primary">— {e.relation} →</span>
                              {to.label}
                            </p>
                            <blockquote className="mt-1.5 border-l-2 border-primary/40 pl-2 text-[11px] leading-relaxed text-muted-foreground">
                              {e.evidence}
                            </blockquote>
                            <p className="mt-1.5 flex items-center gap-1 font-mono text-[10px] text-muted-foreground">
                              <MapPin className="h-3 w-3" />
                              {e.docId}
                            </p>
                          </div>
                        )
                      })}
                    </div>
                  </>
                ) : (
                  <div className="flex h-full min-h-[200px] flex-col items-center justify-center text-center">
                    <p className="text-sm text-muted-foreground">点击图中的节点，查看它的一跳关系、方向与原文证据。</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </Reveal>
        </div>
      </div>
    </section>
  )
}
