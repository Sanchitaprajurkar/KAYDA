import React from 'react'
import {
  Eye,
  Zap,
  Shield,
  Scale,
  Crown,
  CheckCircle2,
  Activity,
  Calendar,
  Layers,
  Sparkles,
  RotateCcw
} from 'lucide-react'
import './TrialProgressBanner.css'

const STAGES = [
  {
    key: 'heimdall',
    agent: 'HEIMDALL',
    role: 'Evidence Gathering',
    rune: 'ᚬ',
    icon: Eye,
    colorClass: 'stage-heimdall'
  },
  {
    key: 'thor',
    agent: 'THOR',
    role: 'High Exposure Prosecution',
    rune: 'ᚦ',
    icon: Zap,
    colorClass: 'stage-thor'
  },
  {
    key: 'loki',
    agent: 'LOKI',
    role: 'Mitigations & Counter-Claims',
    rune: 'ᛚ',
    icon: Shield,
    colorClass: 'stage-loki'
  },
  {
    key: 'odin',
    agent: 'ODIN',
    role: 'Cross-Exam & Judicial Rulings',
    rune: 'ᚩ',
    icon: Scale,
    colorClass: 'stage-odin'
  },
  {
    key: 'verdict',
    agent: 'VERDICT',
    role: 'Executive Intelligence Briefing',
    rune: 'ᛟ',
    icon: Crown,
    colorClass: 'stage-verdict'
  }
]

export default function TrialProgressBanner({
  currentStage = 'thor', // 'heimdall' | 'thor' | 'loki' | 'odin' | 'verdict'
  query,
  asOfDate,
  telemetryLog,
  onOpenBriefing,
  onNewTrial
}) {
  const stageOrder = ['heimdall', 'thor', 'loki', 'odin', 'verdict']
  const currentIndex = stageOrder.indexOf(currentStage)

  return (
    <div className="progress-banner">
      {/* ── Top Bar: Active Inquiry & Parameters ── */}
      <div className="progress-banner__top">
        <div className="progress-banner__inquiry">
          <span className="progress-banner__inquiry-tag">DISRUPTION INQUIRY:</span>
          <span className="progress-banner__inquiry-text" title={query}>
            {query || "What would happen to global semiconductor supply chains if Taiwan's exports were disrupted?"}
          </span>
        </div>

        <div className="progress-banner__meta-row">
          <div className="progress-banner__asof">
            <Calendar size={12} className="progress-banner__icon-gold" />
            <span>As-Of Date: <strong>{asOfDate || '2027-01-25'}</strong></span>
          </div>

          {onNewTrial && (
            <button 
              className="progress-banner__btn-new"
              onClick={onNewTrial}
              title="Configure and start a new disruption inquiry"
            >
              <RotateCcw size={12} />
              <span>New Trial</span>
            </button>
          )}

          <button
            className={`progress-banner__btn-briefing ${currentIndex >= 3 ? 'ready pulse' : ''}`}
            onClick={onOpenBriefing}
          >
            <Crown size={13} />
            <span>Executive Verdict Briefing</span>
          </button>
        </div>
      </div>

      {/* ── 5-Stage Agent Ribbon ── */}
      <div className="progress-banner__ribbon">
        {STAGES.map((stg, idx) => {
          const IconComp = stg.icon
          const isCompleted = idx < currentIndex
          const isActive = idx === currentIndex
          const isPending = idx > currentIndex

          let stateClass = 'pending'
          if (isCompleted) stateClass = 'completed'
          if (isActive) stateClass = 'active'

          return (
            <div
              key={stg.key}
              className={`ribbon-step ${stg.colorClass} ${stateClass}`}
            >
              <div className="ribbon-step__track">
                <div className="ribbon-step__marker">
                  {isCompleted ? (
                    <CheckCircle2 size={13} className="ribbon-step__check" />
                  ) : (
                    <span className="ribbon-step__rune">{stg.rune}</span>
                  )}
                </div>
                {idx < STAGES.length - 1 && (
                  <div className={`ribbon-step__connector ${idx < currentIndex ? 'filled' : ''}`} />
                )}
              </div>

              <div className="ribbon-step__body">
                <div className="ribbon-step__agent-row">
                  <IconComp size={12} className="ribbon-step__agent-icon" />
                  <span className="ribbon-step__agent">{stg.agent}</span>
                  {isActive && <span className="ribbon-step__pulsing-pip" />}
                </div>
                <span className="ribbon-step__role">{stg.role}</span>
              </div>
            </div>
          )
        })}
      </div>

      {/* ── Live Telemetry Log Line ── */}
      <div className="progress-banner__ticker">
        <Activity size={12} className="progress-banner__ticker-icon" />
        <span className="progress-banner__ticker-label">COURT TELEMETRY:</span>
        <span className="progress-banner__ticker-msg">
          {telemetryLog || "All four AI agents operating autonomously. Cross-examination proceedings active in Chamber."}
        </span>
      </div>
    </div>
  )
}
