import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Reveal } from '@/components/Reveal'
import { SectionHeading } from '@/sections/Stats'
import { FEATURES } from '@/data/content'
import { MessageSquareText, BookOpenText, Network, FileSearch } from 'lucide-react'

const ICONS = {
  qa: MessageSquareText,
  lecture: BookOpenText,
  graph: Network,
  trace: FileSearch,
} as const

/** 核心功能区：Origin UI card 风格，低圆角、无营销感 */
export function Features() {
  return (
    <section id="features" className="scroll-mt-20 border-y bg-secondary/40 py-16 sm:py-20">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <SectionHeading
          eyebrow="Features"
          title="四个核心功能"
          desc="所有功能共享同一套可追溯约束：图谱事实与文档片段分区进入上下文，LLM 只能基于检索到的证据组织语言。"
        />
        <div className="mt-10 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map((f, i) => {
            const Icon = ICONS[f.key as keyof typeof ICONS]
            return (
              <Reveal key={f.key} delay={i * 80}>
                <Card className="hover-lift h-full">
                  <CardHeader className="pb-3">
                    <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-md bg-primary/10">
                      <Icon className="h-5 w-5 text-primary" />
                    </div>
                    <CardTitle className="font-serif-sc text-lg">{f.title}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm leading-relaxed text-muted-foreground">{f.desc}</p>
                    <div className="mt-4 flex flex-wrap gap-1.5">
                      {f.tags.map((t) => (
                        <Badge key={t} variant="secondary" className="text-[11px] font-normal">
                          {t}
                        </Badge>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </Reveal>
            )
          })}
        </div>
      </div>
    </section>
  )
}
