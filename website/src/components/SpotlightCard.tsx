import { useRef, type ReactNode } from 'react'

/**
 * SpotlightCard（React Bits / Aceternity 风格）：光标经过时在卡片内投射暖色光影。
 * 通过 CSS 变量 --sx/--sy 定位径向光斑，仅 hover 时显示，克制不霓虹。
 */
export function SpotlightCard({ children, className = '' }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null)

  const onMove = (event: React.MouseEvent<HTMLDivElement>) => {
    const el = ref.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    el.style.setProperty('--sx', `${event.clientX - rect.left}px`)
    el.style.setProperty('--sy', `${event.clientY - rect.top}px`)
  }

  return (
    <div ref={ref} onMouseMove={onMove} className={`spot-card ${className}`}>
      {children}
    </div>
  )
}
