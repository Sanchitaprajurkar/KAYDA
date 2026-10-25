import React from 'react'
import { Check, Search, Zap, Shield, Scale, Crown } from 'lucide-react'
import './TrialTimeline.css'

const STAGES = [
  {
    key: 'heimdall',
    agent: 'Heimdall',
    icon: Search,
    iconEmoji: '🔍',
    description: 'Investigating the disruption and gathering evidence',
    activeStatus: 'Heimdall is investigating the event and collecting evidence across the Nine Realms.',
    colorClass: 'stage-heimdall'
  },
  {
    key: 'thor',
    agent: 'Thor',
    icon: Zap,
    iconEmoji: '⚡',
    description: 'Building the high-exposure argument',
    activeStatus: 'Thor is building the high-exposure prosecution argument.',
    colorClass: 'stage-thor'
  },
  {
    key: 'loki',
    agent: 'Loki',
    icon: Shield,
    iconEmoji: '🐍',
    description: 'Examining mitigating factors and challenging claims',
    activeStatus: 'Loki is examining mitigating factors, buffer stocks, and challenging claims.',
    colorClass: 'stage-loki'
  },
  {
    key: 'odin',
    agent: 'Odin',
    icon: Scale,
    iconEmoji: '⚖️',
    description: 'Evaluating evidence and issuing judicial rulings',
    activeStatus: 'Odin is evaluating the claims and issuing judicial rulings from the High Bench.',
    colorClass: 'stage-odin'
  },
  {
    key: 'verdict',
    agent: 'Final Briefing',
    icon: Crown,
    iconEmoji: '👑',
    description: 'Presenting the verified findings',
    activeStatus: 'Trial concluded. Verified findings, net exposure, and strategic outlook ready.',
    colorClass: 'stage-verdict'
  }
]

export default function TrialTimeline({
  currentStage = 'thor', // 'heimdall' | 'thor' | 'loki' | 'odin' | 'verdict'
  onOpenBriefing
}) {
  const stageKeys = ['heimdall', 'thor', 'loki', 'odin', 'verdict']
  const currentIndex = stageKeys.indexOf(currentStage)
  const activeStageConfig = STAGES[currentIndex >= 0 ? currentIndex : 0]

  return (
    <div className="trial-timeline">
      {/* ── Horizontal 5-Step Tracker ── */}
      <div className="trial-timeline__track">
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
              className={`timeline-step ${stg.colorClass} ${stateClass}`}
              onClick={() => {
                if (stg.key === 'verdict' && (isCompleted || isActive) && onOpenBriefing) {
                  onOpenBriefing()
                }
              }}
              style={{
                cursor: stg.key === 'verdict' && (isCompleted || isActive) ? 'pointer' : 'default'
              }}
            >
              <div className="timeline-step__head">
                <div className="timeline-step__icon-bubble">
                  {isCompleted ? (
                    <Check size={14} className="timeline-step__check-icon" />
                  ) : (
                    <IconComp size={14} className="timeline-step__agent-icon" />
                  )}
                </div>

                <div className="timeline-step__titles">
                  <span className="timeline-step__agent">{stg.agent}</span>
                </div>
              </div>

              <p className="timeline-step__desc">{stg.description}</p>

              {/* Progress connector line */}
              {idx < STAGES.length - 1 && (
                <div className={`timeline-step__connector ${idx < currentIndex ? 'filled' : ''}`} />
              )}
            </div>
          )
        })}
      </div>

      {/* ── Simple Status Message (No internal operations or technical logs) ── */}
      <div className="trial-timeline__status">
        <span className="trial-timeline__status-dot" />
        <span className="trial-timeline__status-text">
          {activeStageConfig.activeStatus}
        </span>
      </div>
    </div>
  )
}
