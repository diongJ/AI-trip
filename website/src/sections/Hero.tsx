import { Link } from 'react-router'

export function Hero() {
  return <section id="top" className="hero scroll-mt-20">
    <div className="hero-seal" aria-hidden>南越</div>
    <div className="hero-copy">
      <p className="hero-kicker">南越数字博物志</p>
      <p className="hero-character">南 越</p>
      <h1>两千年未完的故事</h1>
      <p className="hero-intro">从一方金印、一袭玉衣，走进岭南两千年前的王国。</p>
      <p className="hero-subtitle">AI 智慧导览 · 可追溯知识图谱驱动</p>
      <div className="hero-actions"><a href="#qa" className="ink-button">问一问南越</a><a href="#treasures" className="paper-button">开始探索</a></div>
    </div>
    <Link className="hero-relic" to="/relic/wendi-seal" aria-label="探索文帝行玺">
      <div className="seal-object" aria-hidden><span>文帝<br />行玺</span></div>
      <p>文帝行玺</p><small>金 · 西汉南越国</small>
    </Link>
  </section>
}
