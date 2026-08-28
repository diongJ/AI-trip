import { TIMELINE } from '@/data/museum'

export function Timeline({ onExplore }: { onExplore: (entity: string) => void }) {
  return <section id="timeline" className="museum-section scroll-mt-20 timeline-section">
    <div className="museum-heading"><span>贰</span><div><p>时间维度</p><h2>南越时间长卷</h2></div></div>
    <div className="timeline-track">{TIMELINE.map((item) => <button key={item.year + item.title} onClick={() => onExplore(item.target)} className="timeline-item">
      <span>{item.year}</span><h3>{item.title}</h3><p>{item.text}</p><small>查看相关线索 →</small>
    </button>)}</div>
  </section>
}
