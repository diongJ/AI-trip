import { THEMES } from '@/data/museum'

const SLOT_IMAGES = [
  { src: '/images/sections/theme-seal.png', alt: '文帝行玺金印特写' },
  { src: '/images/sections/theme-jade.png', alt: '南越玉器组合' },
  { src: '/images/sections/theme-lingnan.png', alt: '岭南图景' },
]

export function Themes({ onExplore }: { onExplore: (entity: string) => void }) {
  return <section id="themes" className="museum-section scroll-mt-20 themes-section">
    <div className="museum-heading"><span>陆</span><div><p>主题游览</p><h2>沿着线索继续探索</h2></div></div>
    <div className="theme-grid">{THEMES.map((theme, index) => <article key={theme.title} className="theme-card"><div className="theme-slot"><img src={SLOT_IMAGES[index]?.src} alt={SLOT_IMAGES[index]?.alt ?? theme.title} loading="lazy" /></div><p>{theme.title}</p><h3>{theme.intro}</h3><ol>{theme.stops.map((stop) => <li key={stop}><button onClick={() => onExplore(stop)}>{stop}</button></li>)}</ol></article>)}</div>
  </section>
}
