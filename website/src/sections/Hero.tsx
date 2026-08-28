import { Link } from 'react-router'
import { useEffect, useState } from 'react'
import { RELICS } from '@/data/museum'
import { Clouds } from '@/components/Patterns'

const INTERVAL_MS = 4000

export function Hero() {
  const [index, setIndex] = useState(0)
  const [paused, setPaused] = useState(false)
  const relic = RELICS[index]

  useEffect(() => {
    if (paused) return
    const timer = setInterval(() => setIndex((i) => (i + 1) % RELICS.length), INTERVAL_MS)
    return () => clearInterval(timer)
  }, [paused])

  return <section id="top" className="hero scroll-mt-20">
    <div className="hero-seal" aria-hidden>南越</div>
    <div className="hero-glow" aria-hidden />
    <Clouds className="hero-clouds" />
    <div className="hero-copy">
      <p className="hero-kicker">南越数字博物志</p>
      <p className="hero-character">南 越</p>
      <h1>两千年未完的故事</h1>
      <p className="hero-intro">从一方金印、一袭玉衣，走进岭南两千年前的王国。</p>
      <p className="hero-subtitle">AI 智慧导览 · 可追溯知识图谱驱动</p>
      <div className="hero-actions"><a href="#qa" className="ink-button">问一问南越</a><a href="#treasures" className="paper-button">开始探索</a></div>
      <div className="hero-slot"><img src="/images/sections/hero-hall.png" alt="南越王博物院展厅" loading="lazy" /></div>
    </div>
    <div className="hero-relic" onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)}>
      <Link className="hero-showcase" to={`/relic/${relic.slug}`} aria-label={`探索${relic.name}`}>
        <div className="hero-stage" aria-hidden>
          <span className="hero-counter">0{index + 1} / 0{RELICS.length}</span>
          {RELICS.map((item, i) => <img key={item.slug} src={item.image} alt={i === index ? item.name : ''} className={i === index ? 'active' : ''} loading={i === 0 ? 'eager' : 'lazy'} />)}
        </div>
        <div className="hero-caption" key={relic.slug}>
          <p>{relic.name}</p><small>{relic.material} · {relic.period}</small>
        </div>
      </Link>
      <div className="hero-dots" role="tablist" aria-label="切换展示文物">
        {RELICS.map((item, i) => <button key={item.slug} className={i === index ? 'active' : ''} onClick={() => setIndex(i)} aria-label={`显示${item.name}`} aria-selected={i === index} title={item.name} />)}
      </div>
    </div>
  </section>
}
