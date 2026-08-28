import { Link } from 'react-router'
import { RELICS } from '@/data/museum'

export function Treasures() {
  return <section id="treasures" className="museum-section scroll-mt-20">
    <div className="museum-heading"><span>壹</span><div><p>从一件文物开始</p><h2>镇馆之珍</h2></div></div>
    <div className="relic-scroll" role="list">
      {RELICS.map((relic, index) => <Link key={relic.slug} to={`/relic/${relic.slug}`} className="relic-card" role="listitem">
        <div className={`relic-placeholder relic-${index}`} aria-hidden><span>{relic.imageLabel}</span></div>
        <p className="relic-index">{String(index + 1).padStart(2, '0')} · {relic.theme}</p>
        <h3>{relic.name}</h3><p className="relic-meta">{relic.material} · {relic.period}</p>
        <p className="relic-hover">{relic.place}</p>
      </Link>)}
    </div>
  </section>
}
