/**
 * 花纹组件：回纹分隔带 / 云气纹水印 / 点阵网格
 * 全部为自制 CSS/SVG，无外部资源；参考 Aceternity DotPattern、传统回纹与云气纹。
 */
export function Meander({ className = '' }: { className?: string }) {
  return <div className={`meander ${className}`} aria-hidden />
}

export function Clouds({ className = '' }: { className?: string }) {
  return <div className={`cloud-mark ${className}`} aria-hidden />
}

export function DotGrid({ className = '' }: { className?: string }) {
  return <div className={`dot-grid ${className}`} aria-hidden />
}
