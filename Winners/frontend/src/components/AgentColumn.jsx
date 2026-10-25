import React from 'react'
import {
  ArrowRight,
  BookOpen,
  Zap,
  Shield,
  AlertTriangle,
  CheckCircle2,
  Swords,
  Scale,
  FileText,
  CornerDownRight,
  Hourglass
} from 'lucide-react'
import './AgentColumn.css'

export default function AgentColumn({
  agent,
  claims = [],
  attacks = [],
  defenses = [],
  opposingAttacks = [],
  onCiteClick,
  isResearching = false
}) {
  const isThor = agent === 'THOR'
  const portraitUrl = isThor ? '/thor_avatar.jpg' : '/loki_avatar.jpg'

  // Character metadata & clear role labeling
  const title = isThor ? 'Thor Odinson' : 'Loki Laufeyson'
  const role = isThor ? 'High-Exposure Prosecution' : 'Limited-Exposure Defense'
  const thesisTitle = isThor ? 'High-Exposure Prosecution Stance' : 'Limited-Exposure Defense Stance'

  const thesisSummary = isThor
    ? 'Full suspension of the Orvan corridor triggers immediate supply deficits across Midgard, with forward contract replacement costs escalating up to +18% and catastrophic feedgrain shortfalls.'
    : "Tolan's 68-day buffer reserves and the Vethian overland rail corridor absorb initial quarterly shock, mitigating net exposure to manageable bounds and preventing acute food security failure."

  const keyFactorLabel = isThor ? 'Potential Disruptions:' : 'Mitigating Factors:'
  const keyFactorValue = isThor
    ? 'Midgard Wheat (-54%) & Maize Feed Shortfall (-45% to -55%)'
    : '68-Day Reserves & Vethian Route Diversion (30%–35%)'

  // Default cross-examination fallback if not yet loaded from backend
  const defaultAttack = isThor
    ? {
        target: 'Loki Claim LK-02 (Rail Link)',
        text: "Vantro Trading explicitly confirmed the Ravik Rail Link can handle 'only a fraction' of maritime bulk volumes, and Vanir wheat carries severe price premiums with scarce parcel availability.",
        citations: ['ORV-0001', 'ORV-0006']
      }
    : {
        target: 'Thor Claim TH-01 (Supply Collapse)',
        text: "Thor conflates sea-berth transit drops with total commercial supply destruction. Document ORV-0006 proves millers find the arrangement 'workable' and the Ministry has not changed stock level guidance.",
        citations: ['ORV-0006', 'ORV-0001']
      }

  const defaultDefense = isThor
    ? {
        target: 'Response to Loki Counterargument',
        action: 'CONCEDE & REBUT',
        text: 'Thor concedes that emergency rail transport prevents absolute zero-volume starvation, but maintains commercial exposure remains severe due to higher logistics costs and 60%+ sea volume loss.',
        citations: ['ORV-0006']
      }
    : {
        target: 'Response to Thor Counterargument',
        action: 'CONCEDE & REBUT',
        text: 'Loki concedes rail cannot match 100% of bulk maritime capacity at parity cost, but proves commercial substitution cushions net exposure well below Thor catastrophic 62% bound.',
        citations: ['ORV-0001', 'ORV-0006']
      }

  // Active attacks and defenses from props or defaults
  const activeAttack = attacks.length > 0
    ? {
        target: attacks[0].target_claim_id || (isThor ? 'LK-R1-02' : 'TH-R1-01'),
        text: attacks[0].argument,
        citations: attacks[0].counter_citations || []
      }
    : defaultAttack

  const activeDefense = defenses.length > 0
    ? {
        target: defenses[0].target_claim_id || 'Counterargument',
        action: defenses[0].action || 'DEFEND',
        text: defenses[0].reasoning,
        citations: defenses[0].new_citations || []
      }
    : defaultDefense

  return (
    <div className={`advocate-chamber ${isThor ? 'advocate-chamber--thor' : 'advocate-chamber--loki'}`}>
      {/* ── Advocate Sanctuary Header ── */}
      <div className="advocate-chamber__header">
        <div className="advocate-chamber__portrait-frame">
          <img
            src={portraitUrl}
            alt={title}
            className="advocate-chamber__portrait"
            onError={(e) => { e.currentTarget.style.display = 'none' }}
          />
          <div className="advocate-chamber__halo" />
        </div>

        <div className="advocate-chamber__profile">
          <div className="advocate-chamber__name-row">
            <h2 className="advocate-chamber__name">{title}</h2>
            <span className="advocate-chamber__pip" />
          </div>
          <div className="advocate-chamber__role-badge">
            {role}
          </div>
        </div>
      </div>

      {/* ── Core Argument Thesis Card ── */}
      <div className="advocate-chamber__thesis-card">
        <div className="advocate-chamber__thesis-top">
          <span className="advocate-chamber__thesis-tag">{thesisTitle}</span>
          <span className="advocate-chamber__thesis-bound">
            {isThor ? 'Max Bound: +$310M (+62%)' : 'Net Bound: -$100M (15-25%)'}
          </span>
        </div>
        <p className="advocate-chamber__thesis-body">{thesisSummary}</p>

        <div className="advocate-chamber__thesis-factor">
          <span className="advocate-chamber__factor-label">{keyFactorLabel}</span>
          <span className="advocate-chamber__factor-val">{keyFactorValue}</span>
        </div>
      </div>

      {/* ── Scrollable Testaments, Claims, Evidence & Cross-Examinations ── */}
      <div className="advocate-chamber__scroll">
        <div className="advocate-chamber__section-label">
          <span>Key Claims & Supporting Evidence</span>
          <span className="advocate-chamber__claims-count">
            {claims.length} {claims.length === 1 ? 'Filed Claim' : 'Filed Claims'}
          </span>
        </div>

        {/* ── If Researching: Calm Status Message ── */}
        {isResearching && (
          <div className="advocate-chamber__research-state animate-fade-in">
            <div className="advocate-chamber__research-spinner">
              {isThor ? <Zap size={15} /> : <Shield size={15} />}
            </div>
            <p className="advocate-chamber__research-text">
              {isThor
                ? 'Thor is analyzing trade manifests, calculating high-exposure claims and sea-cargo deficits…'
                : 'Loki is examining buffer stocks, alternate transit routes and calculating mitigation offsets…'}
            </p>
          </div>
        )}

        {/* ── If Not Researching and No Claims: Empty State ── */}
        {!isResearching && claims.length === 0 && (
          <div className="advocate-chamber__empty-state animate-fade-in">
            <Hourglass size={18} className="advocate-chamber__empty-icon" />
            <h4 className="advocate-chamber__empty-title">
              Awaiting argument from {isThor ? 'Thor' : 'Loki'}…
            </h4>
            <p className="advocate-chamber__empty-desc">
              Advocate is examining authenticated exhibits and preparing formal quantitative claims for the High Bench.
            </p>
          </div>
        )}

        {/* ── Claims List ── */}
        {claims.length > 0 && (
          <div className="advocate-chamber__testaments">
            {claims.map((claim, idx) => {
              const claimId = claim.claim_id || claim.id || `CLM-0${idx + 1}`
              const statementText = claim.statement || claim.claim || 'Assertive claim filed to the Bench.'
              const numericalEst = claim.numerical_estimate || claim.exposureRange || claim.exposureImpact
              const claimStatus = (claim.status || 'PENDING').toUpperCase()
              const claimType = claim.claim_type ? claim.claim_type.replace('_', ' ') : (isThor ? 'SOURCED FACT' : 'INFERENCE')

              // Normalize citations array
              const citationsList = Array.isArray(claim.citations) && claim.citations.length > 0
                ? claim.citations
                : (claim.docCitation ? [claim.docCitation] : [])

              const snippets = claim.citation_snippets || []

              return (
                <article key={claimId} className="testament-card animate-fade-in">
                  {/* Card Meta: Simple Claim Index, Claim Code & Badges */}
                  <div className="testament-card__meta">
                    <div className="testament-card__meta-left">
                      <span className="testament-card__order">Pleading {idx + 1}</span>
                      <span className="testament-card__code">{claimId}</span>
                    </div>

                    <div className="testament-card__meta-badges">
                      <span className="testament-card__type-tag">
                        {claimType}
                      </span>
                      <span className={`testament-card__status-tag status-${claimStatus.toLowerCase()}`}>
                        {claimStatus === 'ESTABLISHED' && <CheckCircle2 size={10} />}
                        {claimStatus === 'CONTESTED' && <AlertTriangle size={10} />}
                        <span>{claimStatus}</span>
                      </span>
                    </div>
                  </div>

                  {/* Main Argument Statement */}
                  <p className="testament-card__text">{statementText}</p>

                  {/* Quantified Financial / Operational Scope */}
                  {numericalEst && (
                    <div className="testament-card__scope">
                      <span className="testament-card__scope-label">
                        {isThor ? 'Projected Exposure:' : 'Assessed Mitigation:'}
                      </span>
                      <span className="testament-card__scope-value">
                        {numericalEst}
                      </span>
                    </div>
                  )}

                  {/* Supporting Evidence Snippet (if available) */}
                  {snippets.length > 0 && (
                    <div className="testament-card__snippet-box">
                      <p className="testament-card__snippet-text">{snippets[0]}</p>
                    </div>
                  )}

                  {/* Supporting Evidence Exhibit Links */}
                  {citationsList.length > 0 && (
                    <div className="testament-card__footer">
                      <span className="testament-card__citation-label">Evidence:</span>
                      <div className="testament-card__citation-list">
                        {citationsList.map((docId) => (
                          <button
                            key={docId}
                            className="testament-card__citation-btn"
                            onClick={() => onCiteClick(docId)}
                            title={`Inspect verified Runemark document ${docId}`}
                          >
                            <BookOpen size={11} className="testament-card__citation-icon" />
                            <span>Exhibit {docId}</span>
                            <ArrowRight size={10} className="testament-card__citation-arrow" />
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </article>
              )
            })}
          </div>
        )}

        {/* ── Cross-Examination Counterargument Attack ── */}
        <div className="advocate-chamber__challenge-box">
          <div className="advocate-chamber__challenge-header">
            <Swords size={13} className="advocate-chamber__challenge-icon" />
            <span>
              {isThor ? 'Cross-Examination Attack on Loki' : 'Cross-Examination Attack on Thor'}
            </span>
          </div>
          <div className="advocate-chamber__target-tag">
            Target: {activeAttack.target}
          </div>
          <p className="advocate-chamber__challenge-text">{activeAttack.text}</p>
          {activeAttack.citations && activeAttack.citations.length > 0 && (
            <div className="advocate-chamber__counter-cites">
              <span className="advocate-chamber__counter-label">Counter-Exhibits:</span>
              {activeAttack.citations.map((c) => (
                <button
                  key={c}
                  className="advocate-chamber__cite-chip"
                  onClick={() => onCiteClick(c)}
                >
                  <BookOpen size={10} />
                  <span>{c}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* ── Response to Opposing Counterargument (Defense / Concession) ── */}
        <div className="advocate-chamber__defense-box">
          <div className="advocate-chamber__defense-header">
            <CornerDownRight size={13} className="advocate-chamber__defense-icon" />
            <span>
              {isThor ? "Thor's Response to Loki's Challenge" : "Loki's Response to Thor's Challenge"}
            </span>
            <span className="advocate-chamber__action-badge">
              {activeDefense.action}
            </span>
          </div>
          <p className="advocate-chamber__defense-text">{activeDefense.text}</p>
          {activeDefense.citations && activeDefense.citations.length > 0 && (
            <div className="advocate-chamber__counter-cites">
              <span className="advocate-chamber__counter-label">Cited in Defense:</span>
              {activeDefense.citations.map((c) => (
                <button
                  key={c}
                  className="advocate-chamber__cite-chip"
                  onClick={() => onCiteClick(c)}
                >
                  <BookOpen size={10} />
                  <span>{c}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Chamber Footer: Clean Financial / Net Scope Summary ── */}
      <div className="advocate-chamber__footer">
        <span className="advocate-chamber__footer-label">
          {isThor ? 'Prosecution Stance Scope' : 'Defense Assessed Net Exposure'}
        </span>
        <span className="advocate-chamber__footer-val">
          {isThor ? '+$180M — $310M USD (55-62%)' : '-$65M — -$100M Offset (15-25%)'}
        </span>
      </div>
    </div>
  )
}
