import React from 'react'
import { ArrowLeft, Calendar, RotateCcw, Crown } from 'lucide-react'
import './TopBar.css'

export default function TopBar({
  query,
  asOfDate,
  onBackHome,
  onNewTrial,
  onViewBriefing,
  isTrialComplete
}) {
  // Shortened disruption question
  const displayQuery = query
    ? (query.length > 58 ? query.substring(0, 55).trim() + '...' : query)
    : "Taiwan Semiconductor Chokepoint & Supply Chain Disruption"

  return (
    <header className="topbar">
      {/* ── 1. NINE REALMS — Logo and project name ── */}
      <div className="topbar__left">
        {onBackHome && (
          <button 
            onClick={onBackHome}
            className="topbar__home-btn"
            title="Return to Nine Realms Sanctuary"
          >
            <ArrowLeft size={13} />
            <span>Sanctuary</span>
          </button>
        )}

        <div className="topbar__brand">
          <div className="topbar__emblem">
            <svg viewBox="0 0 24 24" className="topbar__emblem-svg" fill="none">
              <path 
                d="M12 2L3 7V12C3 17.5 7 21.8 12 23C17 21.8 21 17.5 21 12V7L12 2Z" 
                stroke="url(#emblemGoldGradient)" 
                strokeWidth="1.5" 
                strokeLinecap="round" 
                strokeLinejoin="round" 
              />
              <path 
                d="M12 7L16 12H8L12 7Z" 
                fill="url(#emblemGoldGradient)" 
                opacity="0.85" 
              />
              <path 
                d="M12 17L8 12H16L12 17Z" 
                fill="url(#emblemGoldGradient)" 
                opacity="0.6" 
              />
              <defs>
                <linearGradient id="emblemGoldGradient" x1="3" y1="2" x2="21" y2="23" gradientUnits="userSpaceOnUse">
                  <stop stopColor="#F4D388" />
                  <stop offset="0.5" stopColor="#D7AD62" />
                  <stop offset="1" stopColor="#96702E" />
                </linearGradient>
              </defs>
            </svg>
          </div>

          <span className="topbar__title-brand">NINE REALMS</span>
        </div>
      </div>

      {/* ── 2. Current Trial — Shortened disruption question ── */}
      <div className="topbar__center">
        <div className="topbar__trial-info" title={query}>
          <span className="topbar__trial-label">Current Trial</span>
          <span className="topbar__trial-query">{displayQuery}</span>
        </div>
      </div>

      {/* ── 3, 4, 5. As-of Date, New Trial, View Final Briefing ── */}
      <div className="topbar__right">
        {/* As-of Date */}
        <div className="topbar__asof">
          <Calendar size={13} className="topbar__asof-icon" />
          <span>As-of: <strong>{asOfDate || '2027-01-25'}</strong></span>
        </div>

        {/* New Trial */}
        {onNewTrial && (
          <button 
            className="topbar__btn-new"
            onClick={onNewTrial}
            title="Start another disruption analysis"
          >
            <RotateCcw size={12} />
            <span>New Trial</span>
          </button>
        )}

        {/* View Final Briefing — Visible when the trial is complete */}
        {isTrialComplete && (
          <button
            className="topbar__btn-briefing animate-fade-in"
            onClick={onViewBriefing}
            title="Open Sovereign Verdict Executive Briefing"
          >
            <Crown size={13} />
            <span>View Final Briefing</span>
          </button>
        )}
      </div>
    </header>
  )
}
