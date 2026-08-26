import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Reveal } from '@/components/Reveal'
import { BookOpen, GitBranch, ShieldCheck } from 'lucide-react'

/** 首页 Hero：Aceternity UI 风格的静态 Grid + Spotlight 背景，动效克制 */
export function Hero() {
  return (
    <section id="top" className="relative overflow-hidden">
      <div className="bg-grid-ink absolute inset-0" aria-hidden />
      <div className="bg-spotlight absolute inset-0" aria-hidden />
      <div className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-background to-transparent" aria-hidden />

      <div className="relative mx-auto flex max-w-4xl flex-col items-center px-4 pb-20 pt-20 text-center sm:pt-28">
        <Reveal>
          <Badge variant="outline" className="mb-6 gap-1.5 border-primary/30 bg-card px-3 py-1 text-xs">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-primary" aria-hidden />
            覆盖范围：南越专题 · 博物院 / 南越国历史 / 考古与文物
          </Badge>
        </Reveal>

        <Reveal delay={100}>
          <h1 className="font-serif-sc text-3xl font-bold leading-tight tracking-wide sm:text-5xl sm:leading-snug">
            南越王博物院
            <br />
            <span className="text-primary">知识图谱</span>与智慧导览
          </h1>
        </Reveal>

        <Reveal delay={200}>
          <p className="mt-6 max-w-2xl text-sm leading-relaxed text-muted-foreground sm:text-base">
            一个基于可靠资料、知识图谱与 RAG 的可追溯导览系统。
            所有回答均以 181 份分层可信资料（含 36 份核心馆方资料与参观攻略）为据，经由 78 个实体、87 条关系构成的知识图谱
            与文档检索协同生成——每个事实都能回到出处，证据不足时明确拒答。
          </p>
        </Reveal>

        <Reveal delay={300}>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Button asChild size="lg">
              <a href="#qa">体验智能问答</a>
            </Button>
            <Button asChild variant="outline" size="lg" className="hover-lift">
              <a href="#graph">探索知识图谱</a>
            </Button>
          </div>
        </Reveal>

        <Reveal delay={400}>
          <div className="mt-12 grid w-full max-w-2xl grid-cols-1 gap-3 text-left sm:grid-cols-3">
            {[
              { icon: BookOpen, text: '181 份分层可信资料，含 36 份核心馆方资料' },
              { icon: GitBranch, text: 'KG 与 RAG 协同，路由过程可解释' },
              { icon: ShieldCheck, text: '证据不足时拒答，绝不编造答案' },
            ].map(({ icon: Icon, text }) => (
              <div key={text} className="hover-lift flex items-start gap-2.5 rounded-lg border bg-card px-4 py-3">
                <Icon className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                <span className="text-xs leading-relaxed text-muted-foreground">{text}</span>
              </div>
            ))}
          </div>
        </Reveal>
      </div>
    </section>
  )
}
