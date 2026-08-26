import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Reveal } from '@/components/Reveal'
import { SectionHeading } from '@/sections/Stats'
import { EVAL_V2 } from '@/data/content'
import { ShieldCheck, CheckCircle2 } from 'lucide-react'

/** 评测与可靠性区：展示 data/evaluation/summary_v2.json 的 90 题实测结果 */
export function Evaluation() {
  return (
    <section id="evaluation" className="scroll-mt-20 border-t bg-secondary/40 py-16 sm:py-20">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <SectionHeading
          eyebrow="Evaluation"
          title="评测与可靠性"
          desc="90 道评测题对升级后的南越专题问答系统实测，五项指标全部达标。原始结果保存在 data/evaluation/raw_results/，汇总可由脚本重新计算。"
        />

        <Reveal className="mt-10">
          <Card>
            <CardContent className="p-5 sm:p-8">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h3 className="font-serif-sc text-lg font-bold">专题升级版问答系统 · 评测 v2</h3>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    181 份分层可信语料 · 离线抽取式生成模式 · {EVAL_V2.questionCount} 题
                  </p>
                </div>
                <Badge variant="outline" className="gap-1 border-accent/50 text-[11px] text-accent">
                  <CheckCircle2 className="h-3 w-3" />
                  全部指标达标
                </Badge>
              </div>

              <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
                {EVAL_V2.metrics.map((m) => (
                  <div key={m.name}>
                    <div className="flex items-baseline justify-between">
                      <span className="text-xs font-medium text-muted-foreground">{m.name}</span>
                      <span className="font-serif-sc text-sm font-bold text-primary">
                        {m.value}%
                        <span className="ml-1.5 text-[10px] font-normal text-muted-foreground">
                          目标 ≥{m.target}%
                        </span>
                      </span>
                    </div>
                    <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-primary transition-all duration-700"
                        style={{ width: `${m.value}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-6 flex flex-wrap items-center gap-x-6 gap-y-2 border-t pt-4 text-[11px] text-muted-foreground">
                <span>P95 延迟：{EVAL_V2.p95LatencyMs} ms（离线模式）</span>
                <span>DeepSeek 在线端到端实测：约 6.7s（目标 P95 &lt; 15s）</span>
                <span>{EVAL_V2.note}</span>
              </div>
            </CardContent>
          </Card>
        </Reveal>

        <Reveal delay={100}>
          <div className="mt-6 flex items-start gap-3 rounded-lg border bg-card p-4 sm:p-5">
            <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
            <div>
              <h3 className="text-sm font-semibold">拒答机制与证据约束</h3>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                当检索证据不足以支撑回答时，系统明确输出「当前可靠资料不足以确认」，并标注拒答原因，
                而不是让模型自由发挥。配置 DeepSeek 后，本地无证据时可返回带明确标注的通用回答，
                绝不伪装成本地引用答案。90 题评测中拒答准确率 100%、引用正确率 100%——
                回答中的每个事实都能定位到具体文档编号、原文片段与来源链接。
              </p>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  )
}
