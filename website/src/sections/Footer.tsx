import { Separator } from '@/components/ui/separator'

const LINKS = [
  { label: '在线 Demo（Streamlit）', href: '#' },
  { label: 'GitHub 仓库', href: 'https://github.com/diongJ/AI-trip' },
  { label: '评测报告', href: '#' },
  { label: '演示视频', href: '#' },
]

export function Footer() {
  return (
    <footer className="border-t bg-background">
      <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
        <div className="grid grid-cols-1 gap-8 md:grid-cols-[1.4fr_1fr]">
          <div>
            <div className="flex items-center gap-2.5">
              <span className="flex h-8 w-8 items-center justify-center rounded-md bg-primary font-serif-sc text-base font-bold text-primary-foreground">
                越
              </span>
              <span className="font-serif-sc font-semibold">南越王博物院知识图谱与智慧导览</span>
            </div>
            <p className="mt-4 max-w-md text-xs leading-relaxed text-muted-foreground">
              项目范围说明：当前覆盖南越王博物院、南越国历史、考古与文物专题，包含 181 份分层可信资料
              （36 份核心馆方 + 145 份扩展可信与参观攻略）、78 个可靠实体与 87 条可追溯关系。
              不提供实时客流、天气、餐饮和路线导航；可靠性优先于规模，证据不足时系统拒答而非编造。
            </p>
          </div>
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">相关链接</h4>
            <ul className="mt-3 space-y-2">
              {LINKS.map((l) => (
                <li key={l.label}>
                  <a
                    href={l.href}
                    target={l.href.startsWith('http') ? '_blank' : undefined}
                    rel={l.href.startsWith('http') ? 'noreferrer' : undefined}
                    className="text-sm text-foreground/80 underline-offset-4 transition-colors hover:text-primary hover:underline"
                  >
                    {l.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>
        <Separator className="my-8" />
        <p className="text-center text-[11px] text-muted-foreground">
          本站仅用于项目展示 · 所有示例答案均附来源与证据 · 数据口径与仓库、评测报告一致
        </p>
      </div>
    </footer>
  )
}
