/**
 * Marquee 横向滚动条（React Bits 风格）：文物与纹样关键词缓缓流转。
 * 悬停暂停；prefers-reduced-motion 下由全局样式禁用动画。
 */
const ITEMS = ['文帝行玺', '丝缕玉衣', '角形玉杯', '组玉佩', '铜虎节', '船纹铜提筒', '玉舞人', '承盘高足玉杯', '漆木屏风', '南越文王墓', '赵眜', '赵佗']

export function Marquee() {
  const row = [...ITEMS, ...ITEMS]
  return (
    <div className="marquee" aria-hidden>
      <div className="marquee-track">
        {row.map((item, index) => (
          <span key={index} className="marquee-item">{item}<i>◆</i></span>
        ))}
      </div>
    </div>
  )
}
