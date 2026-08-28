import { THEMES } from '@/data/museum'

export function Themes({ onExplore }: { onExplore: (entity: string) => void }) {
  return <section id="themes" className="museum-section scroll-mt-20 themes-section">
    <div className="museum-heading"><span>陆</span><div><p>主题游览</p><h2>沿着线索继续探索</h2></div></div>
    <div className="theme-grid">{THEMES.map((theme) => <article key={theme.title} className="theme-card"><p>{theme.title}</p><h3>{theme.intro}</h3><ol>{theme.stops.map((stop) => <li key={stop}><button onClick={() => onExplore(stop)}>{stop}</button></li>)}</ol></article>)}</div>
  </section>
}
