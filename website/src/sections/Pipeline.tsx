import { Reveal } from '@/components/Reveal'
import { SectionHeading } from '@/sections/Stats'
import { PIPELINE_STEPS } from '@/data/content'
import { ArrowRight } from 'lucide-react'

/** 方法流程区：资料 → 抽取 → 消歧 → 图谱 → RAG → Agent → 有来源回答 */
export function Pipeline() {
  return (
    <section id="pipeline" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-16 sm:px-6 sm:py-20">
      <SectionHeading
        eyebrow="Methodology"
        title="从资料到有来源的回答"
        desc="七步主链路。每一步都可独立验证：语料可校验、抽取可审计、图谱可重建、检索可复算。"
      />

      <div className="mt-12">
        {/* 桌面端：横向流程 */}
        <div className="hidden items-stretch gap-0 lg:flex">
          {PIPELINE_STEPS.map((s, i) => (
            <div key={s.title} className="flex flex-1 items-center">
              <Reveal delay={i * 70} className="w-full">
                <div className="hover-lift flex h-full flex-col rounded-lg border bg-card p-4">
                  <span className="font-serif-sc text-xs font-bold text-primary">
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <h3 className="mt-1.5 text-sm font-semibold">{s.title}</h3>
                  <p className="mt-1.5 text-[11px] leading-relaxed text-muted-foreground">{s.desc}</p>
                </div>
              </Reveal>
              {i < PIPELINE_STEPS.length - 1 && (
                <ArrowRight className="mx-1 h-4 w-4 shrink-0 text-primary/60" aria-hidden />
              )}
            </div>
          ))}
        </div>

        {/* 移动端：纵向时间线 */}
        <div className="relative space-y-4 lg:hidden">
          <div className="absolute bottom-4 left-[15px] top-4 w-px bg-border" aria-hidden />
          {PIPELINE_STEPS.map((s, i) => (
            <Reveal key={s.title} delay={i * 60}>
              <div className="relative flex gap-4 pl-10">
                <span className="absolute left-0 top-0 flex h-8 w-8 items-center justify-center rounded-full border bg-card font-serif-sc text-xs font-bold text-primary">
                  {i + 1}
                </span>
                <div className="flex-1 rounded-lg border bg-card p-4">
                  <h3 className="text-sm font-semibold">{s.title}</h3>
                  <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{s.desc}</p>
                </div>
              </div>
            </Reveal>
          ))}
        </div>
      </div>

      <Reveal delay={150}>
        <p className="mt-10 rounded-lg border border-dashed bg-secondary/40 px-4 py-3 text-center text-xs leading-relaxed text-muted-foreground">
          关键设计约束：LLM 只能基于工具返回的上下文组织语言，不允许把模型自身记忆当作来源；
          输出固定包含 answer、citations、used_tools、route_reason 与 insufficient_evidence 字段。
        </p>
      </Reveal>
    </section>
  )
}
