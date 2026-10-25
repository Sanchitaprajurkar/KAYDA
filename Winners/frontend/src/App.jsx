import React, { useState, useEffect } from 'react'
import Homepage from './components/Homepage'
import TopBar from './components/TopBar'
import AgentColumn from './components/AgentColumn'
import RouteMap from './components/RouteMap'
import OdinBench from './components/OdinBench'
import DocDrawer from './components/DocDrawer'
import {
  TRIAL_META,
  THOR_CLAIMS,
  LOKI_CLAIMS,
  ODIN_FINDINGS,
} from './data/trialData'
import './App.css'

export default function App() {
  const [viewMode, setViewMode] = useState('homepage')
  const [activeDoc, setActiveDoc] = useState(null)

  useEffect(() => {
    const handleHash = () => {
      if (window.location.hash === '#arena' || window.location.hash === '#trial') {
        setViewMode('arena')
      } else if (window.location.hash === '#home' || window.location.hash === '') {
        setViewMode('homepage')
      }
    }
    handleHash()
    window.addEventListener('hashchange', handleHash)
    return () => window.removeEventListener('hashchange', handleHash)
  }, [])

  const enterArena = () => {
    setViewMode('arena')
    window.location.hash = 'arena'
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const returnHome = () => {
    setViewMode('homepage')
    window.location.hash = 'home'
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  if (viewMode === 'homepage') {
    return (
      <Homepage onEnterArena={enterArena} />
    )
  }

  return (
    <div className="trial-layout animate-fade-in">
      {/* ── Global Header ── */}
      <TopBar 
        meta={TRIAL_META} 
        onBackHome={returnHome}
      />

      {/* ── 3-Column Trial Arena ── */}
      <div className="trial-arena">
        {/* Thor */}
        <div className="trial-arena__col">
          <AgentColumn
            agent="THOR"
            claims={THOR_CLAIMS}
            onCiteClick={setActiveDoc}
          />
        </div>

        {/* Center: Route Map */}
        <div className="trial-arena__center">
          <RouteMap />
        </div>

        {/* Loki */}
        <div className="trial-arena__col">
          <AgentColumn
            agent="LOKI"
            claims={LOKI_CLAIMS}
            onCiteClick={setActiveDoc}
          />
        </div>
      </div>

      {/* ── Odin's Verdict Bench (bottom shelf) ── */}
      <OdinBench
        findings={ODIN_FINDINGS}
        meta={TRIAL_META}
        onDocClick={setActiveDoc}
      />

      {/* ── Evidence Drawer (slide-in) ── */}
      <DocDrawer
        docId={activeDoc}
        onClose={() => setActiveDoc(null)}
      />
    </div>
  )
}
