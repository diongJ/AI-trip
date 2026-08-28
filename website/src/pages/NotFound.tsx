import { Link } from 'react-router'
import { Navbar } from '@/sections/Navbar'

export default function NotFound() {
  return (
    <>
      <Navbar />
      <main className="detail-page not-found">
        <p className="hero-kicker">404 · 未收录</p>
        <h1 className="font-serif-sc" style={{ fontSize: 'clamp(34px,5vw,56px)', letterSpacing: '.1em', margin: '12px 0' }}>这里没有展品</h1>
        <p style={{ color: '#63594d' }}>这个页面不在展区里，回首页继续探索吧。</p>
        <Link className="ink-button" to="/" style={{ justifySelf: 'center' }}>回到首页</Link>
      </main>
    </>
  )
}
