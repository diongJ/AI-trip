import { Card, CardContent } from '@/components/ui/card'
import { Reveal } from '@/components/Reveal'
import { CountUp } from '@/components/CountUp'
import { PROJECT_STATS } from '@/data/content'

function SectionHeading({ eyebrow, title, desc }: { eyebrow: string; title: string; desc?: string }) {
  return (
    <Reveal className="mx-auto max-w-2xl text-center">
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">{eyebrow}</p>
      <h2 className="mt-2 font-serif-sc text-2xl font-bold sm:text-3xl">{title}</h2>
      {desc && <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{desc}</p>}
    </Reveal>
  )
}

/** 数据可信区：Origin UI stats / metric 风格 */
export function Stats() {
  return (
    <section id="data" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-16 sm:px-6 sm:py-20">
      <SectionHeading
        eyebrow="Trustworthy Data"
        title="数据可信，规模如实"
        desc="不追求图谱规模，只保留经得起审计的内容。以下数字与代码、文档、评测报告口径一致。"
      />
      <div className="mt-10 grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        {PROJECT_STATS.map((s, i) => (
          <Reveal key={s.label} delay={i * 80}>
            <Card className="hover-lift h-full">
              <CardContent className="flex h-full flex-col p-5">
                <div className="font-serif-sc text-3xl font-bold text-primary sm:text-4xl">
                  <CountUp value={s.value} />
                  <span className="ml-1 text-base font-normal text-muted-foreground">{s.unit}</span>
                </div>
                <p className="mt-1.5 text-sm font-medium">{s.label}</p>
                <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{s.note}</p>
              </CardContent>
            </Card>
          </Reveal>
        ))}
      </div>
      <Reveal delay={200}>
        <p className="mt-6 text-center text-xs text-muted-foreground">
          可靠性优先于数量：未通过证据审计的内容不会进入图谱，也不会出现在回答中。
        </p>
      </Reveal>
    </section>
  )
}

export { SectionHeading }
