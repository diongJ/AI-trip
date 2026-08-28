import { Navbar } from '@/sections/Navbar'
import { Hero } from '@/sections/Hero'
import { QADemo } from '@/sections/QADemo'
import { GraphExplorer } from '@/sections/GraphExplorer'
import { Footer } from '@/sections/Footer'
import { Treasures } from '@/sections/Treasures'
import { Timeline } from '@/sections/Timeline'
import { Themes } from '@/sections/Themes'
import { Research } from '@/sections/Research'
import { useState } from 'react'

export default function Home() {
  const [requestedEntity, setRequestedEntity] = useState<string>()
  const explore = (entity: string) => setRequestedEntity(entity)
  return (
    <div className="min-h-screen">
      <Navbar />
      <main>
        <Hero />
        <Treasures />
        <QADemo />
        <Timeline onExplore={explore} />
        <GraphExplorer requestedEntity={requestedEntity} onConsumed={() => setRequestedEntity(undefined)} />
        <Themes onExplore={explore} />
        <Research />
      </main>
      <Footer />
    </div>
  )
}
