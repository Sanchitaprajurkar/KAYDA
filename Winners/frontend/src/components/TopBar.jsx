import React from 'react'
import { Activity, Wifi } from 'lucide-react'
import './TopBar.css'

export default function TopBar({ meta, onBackHome }) {
  return (
    <header className="topbar">
      {/* ── Brand + Live ── */}
      <div className="topbar__brand">
        {onBackHome && (
          <button 
            onClick={onBackHome}
            style={{
              background: 'rgba(255, 255, 255, 0.06)',
              border: '1px solid rgba(255, 255, 255, 0.12)',
              color: 'var(--odin-hi)',
              borderRadius: '4px',
              padding: '0.3rem 0.6rem',
              fontSize: '0.72rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem',
              fontWeight: 600,
              fontFamily: 'var(--font-mono)',
              marginRight: '0.5rem'
            }}
            title="Return to Nine Realms Homepage"
          >
            ← HOME
          </button>
        )}
        <div className="topbar__logo">
          <span className="topbar__logo-rune">⚔</span>
          <span>NINE REALMS</span>
          <span className="topbar__divider">//</span>
          <span className="topbar__tagline">TRIBUNAL</span>
        </div>
        <div className="topbar__divider-line" />
        <div className="topbar__live">
          <span className="topbar__live-dot" />
          LIVE ARBITRATION
        </div>
      </div>

      {/* ── Case Metadata ── */}
      <div className="topbar__meta">
        <span className="topbar__meta-tag">{meta.trialId}</span>
        <span className="topbar__meta-sep">/</span>
        <span style={{ color: 'var(--text-primary)', letterSpacing: '0.04em' }}>
          INCIDENT: {meta.incident}
        </span>
        <span className="topbar__meta-sep">/</span>
        <span className="topbar__meta-round">
          ROUND {String(meta.roundCurrent).padStart(2, '0')} OF {String(meta.roundTotal).padStart(2, '0')}
        </span>
      </div>

      {/* ── Stats Ticker ── */}
      <div className="topbar__stats">
        <div className="topbar__stats-item">
          <span>DOCS:</span>
          <span className="topbar__stats-val">{meta.verifiedDocs} VERIFIED</span>
        </div>
        <div className="topbar__divider-line" />
        <div className="topbar__stats-item">
          <Activity size={11} className="topbar__stats-green" />
          <span>LATENCY:</span>
          <span className="topbar__stats-val">{meta.latencyMs}ms</span>
        </div>
        <div className="topbar__divider-line" />
        <div className="topbar__stats-item">
          <span>AS-OF:</span>
          <span className="topbar__stats-val">{meta.asOf}</span>
        </div>
      </div>
    </header>
  )
}
