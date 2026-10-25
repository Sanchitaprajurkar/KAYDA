import React from 'react'
import { ShieldAlert, ShieldCheck, ExternalLink } from 'lucide-react'
import './AgentColumn.css'

const STATUS_COLORS = {
  ACTIVE: 'var(--text-secondary)',
  CONTESTED: 'var(--thor)',
  CONCEDED: 'var(--odin)',
}

export default function AgentColumn({ agent, claims, onCiteClick }) {
  const isThor = agent === 'THOR'
  const color = isThor ? 'var(--thor)' : 'var(--loki)'
  const dim   = isThor ? 'var(--thor-dim)' : 'var(--loki-dim)'
  const Icon  = isThor ? ShieldAlert : ShieldCheck
  const label = isThor ? 'THOR // THE ALARM' : 'LOKI // MITIGATION'
  const badge = isThor ? 'HIGH RISK CLAIMS' : 'COUNTERCLAIMS'

  const total = claims.reduce((acc, c) => {
    const m = c.exposureRange?.match(/\$([\d,]+)M/g)
    if (!m) return acc
    const nums = m.map(s => parseFloat(s.replace(/[$,M]/g, '')))
    return acc + nums[nums.length - 1]
  }, 0)

  return (
    <div className="agent-col">
      {/* Header */}
      <div className="agent-col__header">
        <div className="agent-col__title" style={{ color }}>
          <Icon size={13} />
          {label}
        </div>
        <span
          className="agent-col__badge"
          style={{
            color,
            borderColor: color,
            background: dim,
          }}
        >
          {badge}
        </span>
      </div>

      {/* Claims */}
      <div className="agent-col__list">
        {claims.map((claim) => (
          <div
            key={claim.id}
            className="claim-card"
            style={{ borderLeftColor: color }}
          >
            <div className="claim-card__meta">
              <span className="claim-card__ts">{claim.timestamp}</span>
              <span
                className="claim-card__exposure"
                style={{ color }}
              >
                {claim.exposureImpact}
              </span>
            </div>

            <p className="claim-card__body">{claim.claim}</p>

            {claim.exposureRange && (
              <div
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '10px',
                  color: 'var(--text-secondary)',
                  background: 'var(--bg-panel)',
                  padding: '3px 6px',
                  border: '1px solid var(--border)',
                }}
              >
                RANGE: <span style={{ color: 'var(--text-primary)' }}>{claim.exposureRange}</span>
              </div>
            )}

            <div className="claim-card__footer">
              <button
                className="claim-card__cite-btn"
                style={{ '--hover-color': color }}
                onMouseEnter={e => (e.currentTarget.style.color = color)}
                onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-secondary)')}
                onClick={() => onCiteClick(claim.docCitation)}
              >
                CITED: [{claim.docCitation}]
                <ExternalLink size={9} />
              </button>
              <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                <span className="claim-card__round-tag">R{claim.round}</span>
                <span
                  className="claim-card__status"
                  style={{ color: STATUS_COLORS[claim.status] || 'var(--text-muted)' }}
                >
                  {claim.status}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="agent-col__footer">
        <span className="agent-col__footer-label">
          {isThor ? 'TOTAL DEMAND:' : 'TOTAL OFFSET:'}
        </span>
        <span style={{ color, fontWeight: 700 }}>
          {isThor ? '+' : '-'}~${total.toFixed(0)}M USD
        </span>
      </div>
    </div>
  )
}
