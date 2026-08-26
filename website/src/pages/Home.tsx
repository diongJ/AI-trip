import { Navbar } from '@/sections/Navbar'
import { Hero } from '@/sections/Hero'
import { Stats } from '@/sections/Stats'
import { Features } from '@/sections/Features'
import { QADemo } from '@/sections/QADemo'
import { GraphExplorer } from '@/sections/GraphExplorer'
import { Pipeline } from '@/sections/Pipeline'
import { Evaluation } from '@/sections/Evaluation'
import { Footer } from '@/sections/Footer'

export default function Home() {
  return (
    <div className="min-h-screen">
      <Navbar />
      <main>
        <Hero />
        <Stats />
        <Features />
        <QADemo />
        <GraphExplorer />
        <Pipeline />
        <Evaluation />
      </main>
      <Footer />
    </div>
  )
}
