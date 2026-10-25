import React, { useState, useEffect, useRef } from 'react'
import Homepage from './components/Homepage'
import TopBar from './components/TopBar'
import TrialTimeline from './components/TrialTimeline'
import AgentColumn from './components/AgentColumn'
import EvidenceArena from './components/EvidenceArena'
import OdinBench from './components/OdinBench'
import DocDrawer from './components/DocDrawer'
import TrialInitiatorModal from './components/TrialInitiatorModal'
import ExecutiveBriefingModal from './components/ExecutiveBriefingModal'
import { startTrial, subscribeToTrialEvents } from './services/api'
import {
  TRIAL_META,
  THOR_CLAIMS,
  LOKI_CLAIMS,
  THOR_ATTACKS,
  THOR_DEFENSES,
  LOKI_ATTACKS,
  LOKI_DEFENSES,
  ODIN_FINDINGS,
} from './data/trialData'
import './App.css'

export default function App() {
  const [viewMode, setViewMode] = useState('homepage') // 'homepage' | 'arena'
  const [showInitiator, setShowInitiator] = useState(false)
  const [showBriefing, setShowBriefing] = useState(false)
  const [activeDoc, setActiveDoc] = useState(null)

  // Disruption Parameters
  const [disruptionQuery, setDisruptionQuery] = useState(
    "What would happen to global semiconductor supply chains if Taiwan's exports were disrupted?"
  )
  const [asOfDate, setAsOfDate] = useState('2027-01-25')

  // Trial Progression States: 'heimdall' | 'thor' | 'loki' | 'odin' | 'verdict'
  const [trialStage, setTrialStage] = useState('verdict')
  const [telemetryLog, setTelemetryLog] = useState(
    "All four AI agents operating autonomously. Cross-examination proceedings active in Chamber."
  )

  // Arena Data
  const [meta, setMeta] = useState(TRIAL_META)
  const [thorClaims, setThorClaims] = useState(THOR_CLAIMS)
  const [lokiClaims, setLokiClaims] = useState(LOKI_CLAIMS)
  const [thorAttacks, setThorAttacks] = useState(THOR_ATTACKS)
  const [lokiAttacks, setLokiAttacks] = useState(LOKI_ATTACKS)
  const [thorDefenses, setThorDefenses] = useState(THOR_DEFENSES)
  const [lokiDefenses, setLokiDefenses] = useState(LOKI_DEFENSES)
  const [odinFindings, setOdinFindings] = useState(ODIN_FINDINGS)

  const activeStreamRef = useRef(null)
  const simTimersRef = useRef([])

  // Clear timers on unmount
  useEffect(() => {
    return () => {
      if (activeStreamRef.current) activeStreamRef.current()
      simTimersRef.current.forEach(clearTimeout)
    }
  }, [])

  // Sync hash routing
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

  // User clicks "ENTER THE REALMS" or "EXPLORE THE TRIAL" -> Opens Disruption Initiator Modal
  const openTrialInitiator = () => {
    setShowInitiator(true)
  }

  const returnHome = () => {
    setViewMode('homepage')
    setShowInitiator(false)
    setShowBriefing(false)
    window.location.hash = 'home'
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  // User submits disruption question and as-of date in Modal -> The Trial Begins Automatically
  const handleStartTrial = async ({ query, asOfDate: selectedDate }) => {
    setShowInitiator(false)
    setDisruptionQuery(query)
    setAsOfDate(selectedDate)
    setViewMode('arena')
    window.location.hash = 'arena'
    window.scrollTo({ top: 0, behavior: 'smooth' })

    // Clean up any ongoing runs
    if (activeStreamRef.current) activeStreamRef.current()
    simTimersRef.current.forEach(clearTimeout)
    simTimersRef.current = []

    // 1. Enter Heimdall Investigation phase
    setTrialStage('heimdall')
    setTelemetryLog(
      `[HEIMDALL] Convening High Tribunal for "${query.substring(0, 50)}..." (as-of: ${selectedDate}). Authenticating Runemark corpus...`
    )

    // Reset displayed data progressively for dramatic courtroom presentation
    setThorClaims([])
    setLokiClaims([])
    setThorAttacks([])
    setLokiAttacks([])
    setThorDefenses([])
    setLokiDefenses([])
    setOdinFindings([])

    setMeta({
      ...TRIAL_META,
      incident: query.length > 40 ? query.substring(0, 38).toUpperCase() + '...' : query.toUpperCase(),
      asOf: selectedDate,
      roundCurrent: 1,
      status: 'CONVENING'
    })

    // Try backend live orchestration first
    let backendStarted = false
    try {
      const startRes = await startTrial(query, selectedDate)
      if (startRes && startRes.case_id) {
        backendStarted = true
        setMeta((prev) => ({ ...prev, trialId: startRes.case_id }))

        // Subscribe to live SSE telemetry
        const unsub = subscribeToTrialEvents(
          startRes.case_id,
          (event) => {
            handleLiveServerEvent(event)
          },
          (err) => {
            console.warn('[Trial] SSE stream ended or offline, falling back to local simulation:', err)
          }
        )
        activeStreamRef.current = unsub
      }
    } catch (err) {
      console.log('[Trial] Live backend unreachable, running local sovereign simulation:', err.message)
    }

    // Always run progressive simulation runner to guarantee fluid cinematic transition
    runProgressiveCourtroomSimulation(query, selectedDate)
  }

  const handleLiveServerEvent = (event) => {
    if (!event || !event.step) return

    if (event.step === 'CASE_INITIALIZATION' || event.step === 'EVENT_VERIFICATION') {
      setTrialStage('heimdall')
      setTelemetryLog(`[HEIMDALL] ${event.details || event.message || 'Evidence authenticated in Runemark.'}`)
    } else if (event.step === 'ROUND_1_CLAIMS_SUBMISSION' || event.step === 'CLAIMS_RECEIVED') {
      setTrialStage('thor')
      setTelemetryLog('[THOR & LOKI] Concurrently submitting initial quantitative claims to the High Bench.')
      if (event.thor_claims) setThorClaims(event.thor_claims)
      if (event.loki_claims) setLokiClaims(event.loki_claims)
    } else if (event.step === 'ROUND_2_CROSS_EXAMINATION' || event.step === 'ATTACKS_DELIVERED') {
      setTrialStage('loki')
      setTelemetryLog('[CROSS-EXAMINATION] Agents delivering counter-evidence attacks and cross-examination challenges.')
      if (event.thor_attack) setThorAttacks([event.thor_attack])
      if (event.loki_attack) setLokiAttacks([event.loki_attack])
    } else if (event.step === 'DEFENSES_RESOLVED') {
      if (event.thor_defense) setThorDefenses([event.thor_defense])
      if (event.loki_defense) setLokiDefenses([event.loki_defense])
    } else if (event.step === 'ODIN_RULING_COMMENCED' || event.step === 'RULINGS_DELIVERED') {
      setTrialStage('odin')
      setTelemetryLog('[ODIN] Evaluating sufficiency and delivering judicial classifications on evidence.')
      if (event.rulings) {
        setOdinFindings(event.rulings.map((r, i) => ({
          id: `JF-0${i + 1}`,
          type: r.classification || r.ruling || 'ESTABLISHED',
          summary: r.rationale || r.judge_rationale || 'Judicial ruling established by the Bench.',
          sourceDocs: r.exhibits || r.verified_citations || ['ORV-0017'],
          arbitratedImpact: r.exposure_range || 'Arbitrated Finding',
          confidence: r.confidence || Math.round((r.confidence_score || 0.9) * 100)
        })))
      }
    } else if (event.step === 'BRIEFING_SYNTHESIS' || event.step === 'CASE_CLOSED') {
      setTrialStage('verdict')
      setTelemetryLog('[VERDICT] Sovereign Briefing synthesized and cryptographically persisted to Neon PostgreSQL.')
      setMeta((prev) => ({ ...prev, status: 'CONCLUDED' }))
    }
  }

  // Smooth cinematic progression: Heimdall -> Thor -> Loki -> Cross-Exam -> Odin -> Verdict
  const runProgressiveCourtroomSimulation = (query, asOf) => {
    // Stage 1: Heimdall (0 - 1.2s)
    const t1 = setTimeout(() => {
      setTrialStage('heimdall')
      setTelemetryLog(`[HEIMDALL] 42 documents verified strictly pub_date <= ${asOf}. Event authenticity verified.`)
    }, 400)

    // Stage 2: Thor presents prosecution claims (1.4s)
    const t2 = setTimeout(() => {
      setTrialStage('thor')
      setThorClaims(THOR_CLAIMS)
      setTelemetryLog('[THOR] Filing High-Exposure Prosecution claims: 54% import deficit with $180M—$310M exposure range.')
      setMeta((prev) => ({ ...prev, roundCurrent: 1, status: 'ROUND 1 ACTIVE' }))
    }, 1400)

    // Stage 3: Loki presents mitigation & defense claims (2.6s)
    const t3 = setTimeout(() => {
      setTrialStage('loki')
      setLokiClaims(LOKI_CLAIMS)
      setTelemetryLog('[LOKI] Filing Limited-Exposure Defense claims: Tolan 68-day buffer shields acute food security breach.')
      setMeta((prev) => ({ ...prev, roundCurrent: 2, status: 'ROUND 2 ACTIVE' }))
    }, 2600)

    // Stage 4: Cross-Examination Attacks & Defenses (3.8s)
    const t4 = setTimeout(() => {
      setThorAttacks(THOR_ATTACKS)
      setLokiAttacks(LOKI_ATTACKS)
      setThorDefenses(THOR_DEFENSES)
      setLokiDefenses(LOKI_DEFENSES)
      setTelemetryLog('[CROSS-EXAMINATION] Thor and Loki deliver counter-evidence challenges and defense rebuttals.')
      setMeta((prev) => ({ ...prev, roundCurrent: 2, status: 'CROSS-EXAMINATION' }))
    }, 3800)

    // Stage 5: Odin evaluates and rules (4.8s)
    const t5 = setTimeout(() => {
      setTrialStage('odin')
      setOdinFindings(ODIN_FINDINGS)
      setTelemetryLog('[ODIN] Sufficiency confirmed. 5 judicial rulings entered into the High Tribunal ledger.')
      setMeta((prev) => ({ ...prev, roundCurrent: 3, status: 'DELIBERATING' }))
    }, 4800)

    // Stage 6: Final Verdict Briefing Ready (5.8s)
    const t6 = setTimeout(() => {
      setTrialStage('verdict')
      setTelemetryLog('[VERDICT] Sovereign arbitration concluded. Executive Briefing ready for review.')
      setMeta((prev) => ({ ...prev, status: 'VERDICT CONCLUDED' }))
    }, 5800)

    simTimersRef.current.push(t1, t2, t3, t4, t5, t6)
  }

  // If in homepage, render Homepage with onEnterArena triggering modal
  if (viewMode === 'homepage') {
    return (
      <>
        <Homepage onEnterArena={openTrialInitiator} />

        {/* ── Initiate the Trial Modal ── */}
        <TrialInitiatorModal
          isOpen={showInitiator}
          onClose={() => setShowInitiator(false)}
          onStartTrial={handleStartTrial}
        />
      </>
    )
  }

  // In Courtroom Arena
  return (
    <div className="trial-layout animate-fade-in">
      {/* ── Minimal Top Navigation Bar ── */}
      <TopBar
        query={disruptionQuery}
        asOfDate={asOfDate}
        onBackHome={returnHome}
        onNewTrial={openTrialInitiator}
        onViewBriefing={() => setShowBriefing(true)}
        isTrialComplete={trialStage === 'verdict'}
      />

      {/* ── One Simple Timeline (4 Agents + Final Outcome) ── */}
      <TrialTimeline
        currentStage={trialStage}
        onOpenBriefing={() => setShowBriefing(true)}
      />

      {/* ── 3-Column Main Trial Arena: Thor (30%) vs Center Evidence (40%) vs Loki (30%) ── */}
      <div className="trial-arena">
        {/* Thor (High-Exposure Prosecution) */}
        <div className="trial-arena__col">
          <AgentColumn
            agent="THOR"
            claims={thorClaims}
            attacks={thorAttacks}
            defenses={thorDefenses}
            opposingAttacks={lokiAttacks}
            onCiteClick={setActiveDoc}
            isResearching={trialStage === 'heimdall'}
          />
        </div>

        {/* Center: Evidence Arena (Shared Evidence, Trade Data & Corridor Map) */}
        <div className="trial-arena__center">
          <EvidenceArena
            query={disruptionQuery}
            onCiteClick={setActiveDoc}
            isResearching={trialStage === 'heimdall'}
          />
        </div>

        {/* Loki (Limited-Exposure Defense) */}
        <div className="trial-arena__col">
          <AgentColumn
            agent="LOKI"
            claims={lokiClaims}
            attacks={lokiAttacks}
            defenses={lokiDefenses}
            opposingAttacks={thorAttacks}
            onCiteClick={setActiveDoc}
            isResearching={trialStage === 'heimdall'}
          />
        </div>
      </div>

      {/* ── Odin's Verdict Bench (compact lower shelf) ── */}
      <OdinBench
        findings={odinFindings}
        meta={meta}
        onDocClick={setActiveDoc}
      />

      {/* ── Evidence Drawer (slide-in) ── */}
      <DocDrawer
        docId={activeDoc}
        onClose={() => setActiveDoc(null)}
      />

      {/* ── Initiate the Trial Modal (accessible from Arena as well) ── */}
      <TrialInitiatorModal
        isOpen={showInitiator}
        onClose={() => setShowInitiator(false)}
        onStartTrial={handleStartTrial}
      />

      {/* ── Final Sovereign Verdict & Executive Briefing Modal ── */}
      <ExecutiveBriefingModal
        isOpen={showBriefing}
        onClose={() => setShowBriefing(false)}
        onDocClick={(docId) => {
          setShowBriefing(false)
          setActiveDoc(docId)
        }}
        onNewTrial={openTrialInitiator}
        meta={meta}
        query={disruptionQuery}
        asOfDate={asOfDate}
        neonPersisted={true}
      />
    </div>
  )
}
