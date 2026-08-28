import { Routes, Route } from 'react-router'
import Home from './pages/Home'
import RelicDetail from './pages/RelicDetail'
import NotFound from './pages/NotFound'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/relic/:slug" element={<RelicDetail />} />
      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}
