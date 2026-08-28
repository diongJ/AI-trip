import { Link, useParams } from 'react-router'
import { useState } from 'react'
import { Navbar } from '@/sections/Navbar'
import { RELICS } from '@/data/museum'
import { QADemo } from '@/sections/QADemo'
import { Clouds } from '@/components/Patterns'
import { ImageSlot } from '@/components/ImageSlot'

export default function RelicDetail() {
  const { slug } = useParams(); const relic = RELICS.find((item) => item.slug === slug); const [style, setStyle] = useState('深度讲解')
  if (!relic) return <><Navbar /><main className="detail-page not-found"><p>这件文物尚未收录。</p><Link className="ink-button" to="/">回到首页</Link></main></>
  return <><Navbar /><main className="detail-page"><Clouds className="detail-clouds" /><Link className="back-link" to="/#treasures">← 镇馆之珍</Link><section className="detail-hero"><div><p className="hero-kicker">{relic.theme}的线索</p><h1>{relic.name}</h1><p className="detail-subtitle">“{relic.importance}”</p><dl><div><dt>年代</dt><dd>{relic.period}</dd></div><div><dt>材质</dt><dd>{relic.material}</dd></div><div><dt>出土</dt><dd>{relic.place}</dd></div></dl></div><div className="detail-object"><img src={relic.image} alt={relic.name} /></div></section>
    <section className="detail-story"><h2>为什么它重要？</h2><p>{relic.importance}</p><div className="detail-line"><span>{relic.relationSeed}</span><i>相关</i><b>{relic.name}</b><i>出土于</i><span>{relic.place}</span></div></section>
    <section className="detail-lecture"><h2>听它讲述</h2><div>{['1分钟导览', '深度讲解', '给孩子听'].map((item) => <button className={style === item ? 'selected' : ''} onClick={() => setStyle(item)} key={item}>{item}</button>)}</div><p>{style === '给孩子听' ? '试着看看：这些小小的玉片，怎样连成一件能覆盖全身的衣服？' : '点击下方提问，把这件文物放进更广阔的南越故事里。'}</p></section>
    <section className="detail-source"><p>原始史料</p><h2>{relic.source.docId} · {relic.source.title}</h2><blockquote>{relic.source.evidence}</blockquote><a href={relic.source.url} target="_blank" rel="noreferrer">前往馆方资料 ↗</a><ImageSlot className="detail-slot" label={`${relic.name}局部特写`} hint="如印钮 / 玉片 / 纹样细节" ratio="16/9" /></section><QADemo /></main></>
}
