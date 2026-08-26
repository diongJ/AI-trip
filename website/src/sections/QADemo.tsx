import { useState } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'
import { Reveal } from '@/components/Reveal'
import { SectionHeading } from '@/sections/Stats'
import { QA_SAMPLES } from '@/data/content'
import { GitBranch, Clock, AlertCircle, ExternalLink, User, CornerDownRight } from 'lucide-react'

const ROUTE_LABEL: Record<string, string> = {
  search_kg: 'search_kg',
  search_documents: 'search_documents',
  hybrid_search: 'hybrid_search',
  拒绝检索: 'no retrieval',
}

/** 智能问答演示区：真实产品界面，含问题、回答、引用、路由与证据 */
export function QADemo() {
  const [activeId, setActiveId] = useState(QA_SAMPLES[0].id)
  const sample = QA_SAMPLES.find((s) => s.id === activeId)!

  return (
    <section id="qa" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-16 sm:px-6 sm:py-20">
      <SectionHeading
        eyebrow="Live Demo"
        title="智能问答演示"
        desc="以下为 scripts/ask.py 离线抽取式生成模式的真实输出，答案原文未做改写——与 Streamlit Demo 在 DeepSeek 不可用时的降级口径一致。点击左侧示例问题切换，查看路由过程、回答与证据来源。"
      />

      <div className="mt-10 grid grid-cols-1 gap-6 lg:grid-cols-[280px_1fr]">
        {/* 示例问题选择（Uiverse 风格微交互按钮，改色适配） */}
        <Reveal>
          <div className="flex flex-col gap-2">
            <p className="mb-1 text-xs font-medium text-muted-foreground">示例问题</p>
            {QA_SAMPLES.map((s) => (
              <button
                key={s.id}
                onClick={() => setActiveId(s.id)}
                className={`group flex items-start gap-2 rounded-lg border px-3.5 py-3 text-left text-sm transition-all duration-200 ${
                  activeId === s.id
                    ? 'border-primary bg-card shadow-sm'
                    : 'border-transparent bg-transparent text-muted-foreground hover:border-border hover:bg-card'
                }`}
              >
                <CornerDownRight
                  className={`mt-0.5 h-3.5 w-3.5 shrink-0 transition-colors ${
                    activeId === s.id ? 'text-primary' : 'text-muted-foreground/50 group-hover:text-primary/60'
                  }`}
                />
                <span>
                  {s.question}
                  <span className="mt-1 block text-[11px] text-muted-foreground/80">{s.category}</span>
                </span>
              </button>
            ))}
          </div>
        </Reveal>

        {/* 对话界面 */}
        <Reveal delay={100}>
          <Card className="overflow-hidden">
            <CardContent className="p-0">
              {/* 用户问题 */}
              <div className="flex items-start gap-3 border-b bg-secondary/50 px-4 py-4 sm:px-6">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-muted">
                  <User className="h-4 w-4 text-muted-foreground" />
                </span>
                <div>
                  <p className="text-sm font-medium">{sample.question}</p>
                  <p className="mt-0.5 text-[11px] text-muted-foreground">{sample.category}类问题</p>
                </div>
              </div>

              {/* 系统回答 */}
              <div className="px-4 py-5 sm:px-6">
                {/* 路由信息 */}
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline" className="gap-1 font-mono text-[11px]">
                    <GitBranch className="h-3 w-3" />
                    {ROUTE_LABEL[sample.route]}
                  </Badge>
                  <Badge variant="outline" className="gap-1 text-[11px]">
                    <Clock className="h-3 w-3" />
                    {sample.latency}
                  </Badge>
                  {sample.insufficient && (
                    <Badge variant="outline" className="gap-1 border-destructive/40 text-[11px] text-destructive">
                      <AlertCircle className="h-3 w-3" />
                      证据不足 · 已拒答
                    </Badge>
                  )}
                </div>
                <p className="mt-2 text-[11px] text-muted-foreground">路由原因：{sample.routeReason}</p>

                <Separator className="my-4" />

                {/* 回答正文：真实系统输出按证据逐条组织，原样展示 */}
                <div className="space-y-2">
                  {sample.answer.split('\n').map((line, i) => (
                    <p key={i} className="text-sm leading-relaxed">
                      {line}
                    </p>
                  ))}
                </div>
                {sample.suggestion && (
                  <p className="mt-3 rounded-md border border-dashed bg-secondary/50 px-3 py-2 text-xs text-muted-foreground">
                    {sample.suggestion}
                  </p>
                )}

                {/* 引用与证据 */}
                {sample.citations && sample.citations.length > 0 && (
                  <div className="mt-5">
                    <p className="mb-2 text-xs font-semibold">来源与证据（{sample.citations.length}）</p>
                    <Accordion type="single" collapsible className="rounded-lg border">
                      {sample.citations.map((c, i) => (
                        <AccordionItem key={i} value={`c-${i}`} className={i === 0 ? 'border-b' : 'border-none'}>
                          <AccordionTrigger className="px-4 py-3 text-left text-xs hover:no-underline">
                            <span className="flex items-center gap-2">
                              <span className="font-mono text-[10px] text-muted-foreground">[{c.docId}]</span>
                              {c.title}
                            </span>
                          </AccordionTrigger>
                          <AccordionContent className="px-4 pb-4">
                            <blockquote className="border-l-2 border-primary/50 pl-3 text-xs leading-relaxed text-muted-foreground">
                              {c.evidence}
                            </blockquote>
                            <a
                              href={c.sourceUrl}
                              target="_blank"
                              rel="noreferrer"
                              className="mt-2 flex items-center gap-1 text-[11px] text-primary underline-offset-2 hover:underline"
                            >
                              <ExternalLink className="h-3 w-3" />
                              {c.source} · {c.sourceUrl}
                            </a>
                          </AccordionContent>
                        </AccordionItem>
                      ))}
                    </Accordion>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
          <div className="mt-4 flex justify-end">
            <Button variant="outline" size="sm" asChild className="hover-lift">
              <a href="https://github.com/diongJ/AI-trip" target="_blank" rel="noreferrer">
                在 GitHub 查看系统实现
              </a>
            </Button>
          </div>
        </Reveal>
      </div>
    </section>
  )
}
