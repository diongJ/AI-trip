import { useState } from 'react'
import { Link } from 'react-router'

const NAV = [['/#top', '首页'], ['/#treasures', '镇馆之珍'], ['/#qa', '问南越'], ['/#kids', '故事屋'], ['/#timeline', '时间长卷'], ['/#relations', '关系探秘'], ['/#research', '研究与技术']]

export function Navbar() {
  const [open, setOpen] = useState(false)
  const links = () => NAV.map(([href, label]) => <a key={href} href={href.replace('/', '')} onClick={() => setOpen(false)}>{label}</a>)
  return <header className="museum-nav"><Link to="/" className="brand"><span>越</span><b>南越数字博物志</b></Link><nav>{links()}</nav><button className="nav-toggle" onClick={() => setOpen(!open)} aria-label="打开导航" aria-expanded={open}>目</button>{open && <div className="mobile-nav">{links()}</div>}</header>
}
