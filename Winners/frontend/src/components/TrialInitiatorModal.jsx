import React, { useState } from 'react'
import {
  Shield,
  Zap,
  Scale,
  Eye,
  Calendar,
  Sparkles,
  ArrowRight,
  X,
  CheckCircle2,
  AlertTriangle
} from 'lucide-react'
import './TrialInitiatorModal.css'

const PRESET_QUERIES = [
  {
    id: 'taiwan',
    title: 'Taiwan Semiconductor Chokepoint',
    category: 'High-Tech / Photonics',
    rune: 'ᚨ',
    query: "What would happen to global semiconductor supply chains if Taiwan's exports were disrupted?",
    asOf: '2027-01-25',
    riskLevel: 'CRITICAL EXPOSURE'
  },
  {
    id: 'orvan',
    title: 'Orvan Grain Corridor Collapse',
    category: 'Agriculture & Food Security',
    rune: 'ᛗ',
    query: "What is the net supply-chain exposure across Midgard and Tolan following the Orvan grain corridor suspension?",
    asOf: '2027-01-25',
    riskLevel: 'HIGH EXPOSURE'
  },
  {
    id: 'suez',
    title: 'Red Sea & Suez Shipping Bottleneck',
    category: 'Maritime Freight Logistics',
    rune: 'ᛁ',
    query: "What is the freight cost escalation, transit delay, and container vessel displacement if the Suez corridor is blocked?",
    asOf: '2027-01-25',
    riskLevel: 'SYSTEMIC FRICTION'
  }
]

export default function TrialInitiatorModal({ isOpen, onClose, onStartTrial }) {
  const [selectedPreset, setSelectedPreset] = useState(PRESET_QUERIES[0].id)
  const [query, setQuery] = useState(PRESET_QUERIES[0].query)
  const [asOfDate, setAsOfDate] = useState('2027-01-25')

  if (!isOpen) return null

  const handleSelectPreset = (preset) => {
    setSelectedPreset(preset.id)
    setQuery(preset.query)
    setAsOfDate(preset.asOf)
  }

  const handleStart = (e) => {
    e.preventDefault()
    if (!query.trim()) return
    onStartTrial({
      query: query.trim(),
      asOfDate: asOfDate || '2027-01-25'
    })
  }

  return (
    <div className="initiator-backdrop animate-fade-in" onClick={onClose}>
      <div 
        className="initiator-modal" 
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-labelledby="initiator-title"
      >
        {/* Subtle Ambient Halos */}
        <div className="initiator-glow-crimson" />
        <div className="initiator-glow-emerald" />

        {/* Modal Header */}
        <div className="initiator-header">
          <div className="initiator-emblem">
            <svg viewBox="0 0 24 24" className="initiator-emblem-svg" fill="none">
              <path 
                d="M12 2L3 7V12C3 17.5 7 21.8 12 23C17 21.8 21 17.5 21 12V7L12 2Z" 
                stroke="url(#initiatorGoldGrad)" 
                strokeWidth="1.5" 
              />
              <path 
                d="M12 7L16 12H8L12 7Z" 
                fill="url(#initiatorGoldGrad)" 
                opacity="0.85" 
              />
              <defs>
                <linearGradient id="initiatorGoldGrad" x1="3" y1="2" x2="21" y2="23" gradientUnits="userSpaceOnUse">
                  <stop stopColor="#F8E5B5" />
                  <stop offset="0.5" stopColor="#D7AD62" />
                  <stop offset="1" stopColor="#96702E" />
                </linearGradient>
              </defs>
            </svg>
          </div>

          <div className="initiator-title-group">
            <div className="initiator-badge">
              <span className="initiator-badge-dot" />
              <span>THE HIGH TRIBUNAL OF ASGARD</span>
            </div>
            <h2 id="initiator-title" className="initiator-title">
              INITIATE THE TRIAL OF THE NINE REALMS
            </h2>
            <p className="initiator-subtitle">
              Configure the disruption inquiry and as-of evaluation date. The four sovereign AI agents will convene automatically.
            </p>
          </div>

          <button 
            className="initiator-close-btn" 
            onClick={onClose}
            aria-label="Close Initiation Modal"
          >
            <X size={18} />
          </button>
        </div>

        {/* Preset Disruption Scenarios */}
        <div className="initiator-section">
          <div className="initiator-section-header">
            <span className="initiator-section-label">Select Disruption Scenario Preset</span>
            <span className="initiator-section-hint">Or compose your custom inquiry below</span>
          </div>

          <div className="initiator-presets-grid">
            {PRESET_QUERIES.map((preset) => {
              const isSelected = selectedPreset === preset.id
              return (
                <button
                  type="button"
                  key={preset.id}
                  className={`initiator-preset-card ${isSelected ? 'active' : ''}`}
                  onClick={() => handleSelectPreset(preset)}
                >
                  <div className="initiator-preset-top">
                    <span className="initiator-preset-rune">{preset.rune}</span>
                    <span className="initiator-preset-risk">{preset.riskLevel}</span>
                  </div>
                  <h4 className="initiator-preset-title">{preset.title}</h4>
                  <span className="initiator-preset-category">{preset.category}</span>
                </button>
              )
            })}
          </div>
        </div>

        {/* Input Form */}
        <form onSubmit={handleStart} className="initiator-form">
          {/* Disruption Question */}
          <div className="initiator-field">
            <label htmlFor="disruption-query" className="initiator-label">
              <span>Disruption Question</span>
              <span className="initiator-label-sub">Specific corridor, commodity, or geopolitical chokepoint</span>
            </label>
            <div className="initiator-textarea-wrap">
              <textarea
                id="disruption-query"
                rows={3}
                className="initiator-textarea"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value)
                  setSelectedPreset(null)
                }}
                placeholder="e.g. What would happen to global semiconductor supply chains if Taiwan's exports were disrupted?"
                required
              />
            </div>
          </div>

          {/* As-Of Date & Temporal Boundaries */}
          <div className="initiator-field">
            <div className="initiator-date-row">
              <div className="initiator-date-group">
                <label htmlFor="as-of-date" className="initiator-label">
                  <Calendar size={13} className="initiator-icon-gold" />
                  <span>As-Of Evaluation Date</span>
                </label>
                <input
                  id="as-of-date"
                  type="date"
                  className="initiator-date-input"
                  value={asOfDate}
                  onChange={(e) => setAsOfDate(e.target.value)}
                  required
                />
              </div>

              <div className="initiator-boundary-pill">
                <AlertTriangle size={13} className="initiator-icon-alert" />
                <span>Strict Temporal Boundary: Documents published after {asOfDate} are inadmissible</span>
              </div>
            </div>
          </div>

          {/* Autonomous Agents Pipeline Strip */}
          <div className="initiator-pipeline-strip">
            <div className="initiator-pipeline-title">
              <span>Autonomous Courtroom Agents Convening</span>
              <span className="initiator-pipeline-role">User is Initiator & Observer</span>
            </div>

            <div className="initiator-agents-row">
              <div className="initiator-agent-item agent-heimdall">
                <div className="initiator-agent-badge">
                  <Eye size={12} />
                  <span>Heimdall</span>
                </div>
                <span className="initiator-agent-task">Investigates & gathers case file evidence</span>
              </div>

              <div className="initiator-agent-item agent-thor">
                <div className="initiator-agent-badge">
                  <Zap size={12} />
                  <span>Thor</span>
                </div>
                <span className="initiator-agent-task">Builds high worst-case exposure case</span>
              </div>

              <div className="initiator-agent-item agent-loki">
                <div className="initiator-agent-badge">
                  <Shield size={12} />
                  <span>Loki</span>
                </div>
                <span className="initiator-agent-task">Argues mitigations, buffers & substitutions</span>
              </div>

              <div className="initiator-agent-item agent-odin">
                <div className="initiator-agent-badge">
                  <Scale size={12} />
                  <span>Odin</span>
                </div>
                <span className="initiator-agent-task">Evaluates claims, tests sufficiency & rules</span>
              </div>
            </div>
          </div>

          {/* Footer Actions */}
          <div className="initiator-actions">
            <button
              type="button"
              className="initiator-btn-cancel"
              onClick={onClose}
            >
              <span>Return to Sanctuary</span>
            </button>

            <button
              type="submit"
              className="initiator-btn-begin"
              disabled={!query.trim()}
            >
              <span>BEGIN TRIAL</span>
              <span className="initiator-btn-rune">⚔</span>
              <ArrowRight size={15} />
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
