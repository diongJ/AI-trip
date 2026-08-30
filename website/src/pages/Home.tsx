import { Navbar } from '@/sections/Navbar'
import { Hero } from '@/sections/Hero'
import { QADemo } from '@/sections/QADemo'
import { KidsQA } from '@/sections/KidsQA'
import { GraphExplorer } from '@/sections/GraphExplorer'
import { Footer } from '@/sections/Footer'
import { Treasures } from '@/sections/Treasures'
import { Timeline } from '@/sections/Timeline'
import { Research } from '@/sections/Research'
import { Meander } from '@/components/Patterns'
import { Marquee } from '@/components/Marquee'
import { useState } from 'react'

export default function Home() {
  const [requestedEntity, setRequestedEntity] = useState<string>()
  const [prefillQuestion, setPrefillQuestion] = useState<string>()
  const explore = (entity: string) => setRequestedEntity(entity)
  const askFromEvidence = (question: string) => {
    setPrefillQuestion(question)
    document.getElementById('qa')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
  return (
    <div className="min-h-screen">
      <Navbar />
      <main>
        <Hero />
        <Meander />
        <Treasures />
        <QADemo prefillQuestion={prefillQuestion} onPrefillConsumed={() => setPrefillQuestion(undefined)} />
        <KidsQA />
        <Marquee />
        <Timeline onExplore={explore} />
        <GraphExplorer requestedEntity={requestedEntity} onConsumed={() => setRequestedEntity(undefined)} onAsk={askFromEvidence} />
        <Research />
        <Meander />
      </main>
      <Footer />
    </div>
  )
}
