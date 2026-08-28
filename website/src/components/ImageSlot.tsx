/**
 * 图片占位槽：虚线框 + 文字说明，用于在设计阶段标注图片位置。
 * 正式图片就绪后，将本组件替换为 <img src="..." /> 并保持同尺寸容器。
 */
export function ImageSlot({ label, hint, ratio = '16/6', className = '' }: { label: string; hint?: string; ratio?: string; className?: string }) {
  return (
    <div className={`img-slot ${className}`} style={{ aspectRatio: ratio }}>
      <span className="img-slot-mark" aria-hidden>◆</span>
      <b>{label}</b>
      <small>{hint ?? '待补图片'}</small>
      <em>{ratio.replace('/', ' : ')} 比例 · 建议高清横向图</em>
    </div>
  )
}
