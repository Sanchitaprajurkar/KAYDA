import React, { useState } from 'react'
import { Scale, ChevronDown, ChevronUp } from 'lucide-react'
import './OdinBench.css'

const TYPE_META = {
  ESTABLISHED: { color: 'var(--odin)',  border: 'var(--odin-border)',  bg: 'var(--odin-dim)'  },
  CONTESTED:   { color: 'var(--thor)',  border: 'var(--thor-border)',  bg: 'var(--thor-dim)'  },
  CONCEDED:    { color: 'var(--loki)',  border: 'var(--loki-border)',  bg: 'var(--loki-dim)'  },
}

export default function OdinBench({ findings, meta, onDocClick }) {
  const [expanded, setExpanded] = useState(true)
  const [activeTab, setActiveTab] = useState('ESTABLISHED')

  const counts = {
    ESTABLISHED: findings.filter(f => f.type === 'ESTABLISHED').length,
    CONTESTED:   findings.filter(f => f.type === 'CONTESTED').length,
    CONCEDED:    findings.filter(f => f.type === 'CONCEDED').length,
  }

  const visible = findings.filter(f => f.type === activeTab)

  return (
    <div className="odin-bench">
      {/* ── Primary bar ── */}
      <div className="odin-bench__bar">
        {/* Left: identity + pills */}
        <div className="odin-bench__identity">
          <div className="odin-bench__title">
            <Scale size={13} />
            ODIN'S VERDICT BENCH
          </div>

          <div className="odin-divider-line" style={{ width:1, height:14, background:'var(--border)' }} />

          <div className="odin-bench__pills">
            {['ESTABLISHED', 'CONTESTED', 'CONCEDED'].map(tab => {
              const m = TYPE_META[tab]
              const active = activeTab === tab
              return (
                <button
                  key={tab}
                  className="odin-pill"
                  style={{
                    color: active ? m.color : 'var(--text-secondary)',
                    borderColor: active ? m.color : 'var(--border)',
                    background: active ? m.bg : 'transparent',
                  }}
                  onClick={() => { setActiveTab(tab); setExpanded(true) }}
                >
                  {tab} ({String(counts[tab]).padStart(2, '0')})
                </button>
              )
            })}
          </div>
        </div>

        {/* Right: final range + confidence + toggle */}
        <div className="odin-bench__right">
          <div className="odin-bench__range">
            <span className="odin-bench__range-label">VERIFIED EXPOSURE:</span>
            <span className="odin-bench__range-val">
              {meta.exposureFinal.min} — {meta.exposureFinal.max} {meta.exposureUnit}
            </span>
            <span className="odin-bench__conf">
              CONFIDENCE: {meta.confidence}%
            </span>
          </div>

          <button
            className="odin-bench__toggle"
            onClick={() => setExpanded(e => !e)}
            aria-label="Toggle findings"
          >
            {expanded
              ? <ChevronDown size={13} />
              : <ChevronUp size={13} />}
          </button>
        </div>
      </div>

      {/* ── Expanded findings shelf ── */}
      {expanded && (
        <div className="odin-bench__shelf">
          <div className="odin-bench__grid">
            {visible.map(finding => {
              const m = TYPE_META[finding.type]
              return (
                <div key={finding.id} className="finding-card">
                  <div className="finding-card__top">
                    <span className="finding-card__id" style={{ color: m.color }}>
                      {finding.id}
                    </span>
                    <span className="finding-card__round">R{finding.round}</span>
                  </div>

                  <p className="finding-card__body">{finding.summary}</p>

                  <div className="finding-card__docs">
                    <span className="finding-card__docs-label">EVIDENCE:</span>
                    {finding.sourceDocs.map(d => (
                      <button
                        key={d}
                        className="finding-card__doc-btn"
                        onClick={() => onDocClick(d)}
                      >
                        [{d}]
                      </button>
                    ))}
                  </div>

                  <div className="finding-card__bottom">
                    <span
                      className="finding-card__impact"
                      style={{ color: m.color }}
                    >
                      {finding.arbitratedImpact}
                    </span>
                    <span className="finding-card__conf">
                      CONF: {finding.confidence}%
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
