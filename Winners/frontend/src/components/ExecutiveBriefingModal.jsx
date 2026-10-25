import React from 'react'
import {
  Scale,
  BookOpen,
  ArrowRight,
  X,
  CheckCircle2,
  AlertTriangle,
  TrendingUp,
  Globe,
  Database,
  FileText,
  Printer,
  ShieldAlert,
  Info
} from 'lucide-react'
import './ExecutiveBriefingModal.css'

export default function ExecutiveBriefingModal({
  isOpen,
  onClose,
  onDocClick,
  onNewTrial,
  meta,
  query,
  asOfDate,
  neonPersisted = true
}) {
  if (!isOpen) return null

  const displayMeta = meta || {
    trialId: 'CASE-NR-2027-E5',
    incident: "Taiwan & Orvan Global Supply Chain Disruption",
    asOf: asOfDate || '2027-01-25',
    exposureFinal: { min: '$87M', max: '$210M' },
    exposureUnit: 'USD Net Arbitrated Exposure',
    confidence: 94
  }

  const citations = [
    {
      id: 'ORV-0017',
      title: 'Orvan corridor: notice of suspension of transit agreement',
      source: 'Runemark Trade Secretariat',
      tier: 'Tier 1 (Government)',
      date: '2027-01-18',
      relevance: 'Official confirmation of transit suspension under force majeure.'
    },
    {
      id: 'ORV-0023',
      title: 'Midgard import dependency matrix — Q4 2026',
      source: 'Midgard Ministry of Trade',
      tier: 'Tier 1 (Government)',
      date: '2026-11-30',
      relevance: 'Establishes Midgard 54% wheat and 38% maize import reliance on the corridor.'
    },
    {
      id: 'ORV-0031',
      title: 'Tolan grain supply strategic assessment',
      source: 'Tolan Bureau of Statistics',
      tier: 'Tier 1 (Government)',
      date: '2027-01-10',
      relevance: 'Validates 68 days of wheat and 45 days of maize buffer reserves in certified silos.'
    },
    {
      id: 'ORV-0044',
      title: 'Vethian overland route feasibility — emergency note',
      source: 'Runemark Freight Exchange',
      tier: 'Tier 2 (Industry Body)',
      date: '2027-01-20',
      relevance: 'Documents 30–35% volume absorption capacity via overland rail corridors.'
    },
    {
      id: 'ORV-0038',
      title: 'Global commodity forward spot-price index',
      source: 'Realm Commodity Exchange',
      tier: 'Tier 2 (Exchange)',
      date: '2027-01-15',
      relevance: 'Surge of +12% in futures and +18% premium on secondary physical contracts.'
    }
  ]

  const countryExposures = [
    {
      country: 'Midgard',
      sector: 'Agriculture (Wheat & Maize)',
      mechanism: 'Direct transit corridor dependency (54% wheat / 38% maize) with no active replacement contracts for Q1 2027.',
      impactRange: '$165M — $290M USD',
      hasRange: true,
      status: 'Established (Critical)',
      tone: 'danger'
    },
    {
      country: 'Tolan',
      sector: 'Agriculture (Maize Feedstock)',
      mechanism: 'Historical import reliance (41% wheat / 29% maize), heavily shielded by sovereign strategic reserve silos.',
      impactRange: '$55M — $110M USD',
      hasRange: true,
      status: 'Established (Buffer Insulated)',
      tone: 'success'
    },
    {
      country: 'Vethi',
      sector: 'Overland Rail Logistics',
      mechanism: 'Alternative bypass route capacity capable of absorbing 30–35% of displaced volume subject to customs fast-track.',
      impactRange: '-$65M — -$90M USD offset',
      hasRange: true,
      status: 'Contested (Under Review)',
      tone: 'warning'
    },
    {
      country: 'Utgard / Peripheral Realms',
      sector: 'Downstream Food Processing',
      mechanism: 'Secondary price inflation transmitted via global commodity spot markets; no direct bilateral supply contracts disrupted.',
      impactRange: 'Insufficient evidence to estimate',
      hasRange: false,
      status: 'Inconclusive',
      tone: 'muted'
    }
  ]

  const handlePrint = () => {
    window.print()
  }

  return (
    <div className="briefing-backdrop animate-fade-in" onClick={onClose}>
      <div 
        className="briefing-document" 
        onClick={(e) => e.stopPropagation()}
        role="document"
        aria-labelledby="briefing-doc-title"
      >
        {/* Document Action Bar */}
        <div className="briefing-doc__action-bar">
          <div className="briefing-doc__status-pill">
            <span className="doc-status-dot" />
            <span>OFFICIAL JUDICIAL BRIEFING · HIGH TRIBUNAL</span>
          </div>

          <div className="briefing-doc__action-btns">
            <button 
              className="briefing-doc__btn"
              onClick={handlePrint}
              title="Print or Export PDF Briefing"
            >
              <Printer size={13} />
              <span>Print Briefing</span>
            </button>
            <button 
              className="briefing-doc__close-btn"
              onClick={onClose}
              aria-label="Close Briefing"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* ── Document Header ── */}
        <header className="briefing-doc__header">
          <div className="briefing-doc__emblem">
            <Scale size={24} />
          </div>

          <div className="briefing-doc__header-text">
            <span className="briefing-doc__asgard-tag">THE HIGH TRIBUNAL OF ASGARD</span>
            <h1 id="briefing-doc-title" className="briefing-doc__title">
              EXECUTIVE INTELLIGENCE BRIEFING
            </h1>
            <p className="briefing-doc__subtitle">
              Adversarial Judicial Arbitration on Global Supply Chain Disruption
            </p>
          </div>

          <div className="briefing-doc__meta-grid">
            <div className="meta-item">
              <span className="meta-label">DOCKET NUMBER</span>
              <span className="meta-val">{displayMeta.trialId || 'CASE-NR-2027-E5'}</span>
            </div>
            <div className="meta-item">
              <span className="meta-label">AS-OF EVALUATION DATE</span>
              <span className="meta-val">{asOfDate || displayMeta.asOf}</span>
            </div>
            <div className="meta-item">
              <span className="meta-label">NET ARBITRATED EXPOSURE</span>
              <span className="meta-val gold-val">
                {displayMeta.exposureFinal.min} — {displayMeta.exposureFinal.max} USD
              </span>
            </div>
            <div className="meta-item">
              <span className="meta-label">JUDICIAL CERTAINTY</span>
              <span className="meta-val">{displayMeta.confidence || 94}% Confidence</span>
            </div>
          </div>

          <div className="briefing-doc__inquiry-banner">
            <span className="inquiry-banner__label">EVALUATED DISRUPTION INQUIRY:</span>
            <span className="inquiry-banner__text">{query || displayMeta.incident}</span>
          </div>
        </header>

        {/* ── Document Body (Clean, Readable Page) ── */}
        <main className="briefing-doc__body">
          {/* ── SECTION 1: EXECUTIVE SUMMARY ── */}
          <section className="briefing-section">
            <h2 className="section-heading">1. Executive Summary</h2>
            <div className="section-prose">
              <p>
                On 18 January 2027, the Joint Transit Committee officially issued notice of the indefinite suspension of the primary Orvan agricultural trade corridor, citing unresolved cross-border customs disputes and declarations of force majeure by signatory states. The disruption takes legal and commercial effect as of 20 January 2027.
              </p>
              <p>
                This suspension carries systemic implications for regional food security, commodity spot pricing, and freight logistics across Midgard, Tolan, and affiliated realms. The tribunal convened four autonomous AI agents—Heimdall (Evidence Intake), Thor (Prosecution), Loki (Mitigation Defense), and Odin (Judicial Bench)—to cross-examine the facts under strict temporal isolation as of <strong>{asOfDate || displayMeta.asOf}</strong>.
              </p>
              <p>
                While initial worst-case prosecution claims argued for catastrophic unhedged liabilities exceeding $310M USD, the High Bench has arbitrated a verified net exposure range between <strong>{displayMeta.exposureFinal.min} and {displayMeta.exposureFinal.max} USD</strong>. This finding directly incorporates 68 days of verified strategic buffer stock insulation and realistic overland bypass absorption.
              </p>
            </div>
          </section>

          {/* ── SECTION 2: KEY FINDINGS ── */}
          <section className="briefing-section">
            <h2 className="section-heading">2. Key Findings</h2>
            <div className="findings-bullet-list">
              <div className="finding-item">
                <div className="finding-num">01</div>
                <div className="finding-content">
                  <h3 className="finding-title">Corridor Suspension Authenticated via Tier-1 Sovereign Gazette</h3>
                  <p className="finding-desc">
                    Notice of suspension confirmed via Runemark Trade Secretariat (Exhibit ORV-0017). Speculative wire bulletins suggesting immediate renewal talks were formally retracted (Exhibit ORV-0013 / WLD-0024) and ruled inadmissible by the Bench.
                  </p>
                </div>
              </div>

              <div className="finding-item">
                <div className="finding-num">02</div>
                <div className="finding-content">
                  <h3 className="finding-title">Critical Import Dependency Established for Midgard</h3>
                  <p className="finding-desc">
                    Official ministry dependency matrices (Exhibit ORV-0023) substantiate that Midgard imports 54% of its wheat and 38% of its maize through the disrupted corridor, holding zero executed substitute contracts for Q1 2027.
                  </p>
                </div>
              </div>

              <div className="finding-item">
                <div className="finding-num">03</div>
                <div className="finding-content">
                  <h3 className="finding-title">Strategic Buffer Reserves Insulate Acute Food Security Breach</h3>
                  <p className="finding-desc">
                    Verified statistical filings (Exhibit ORV-0031) confirm Tolan holds 68 days of wheat and 45 days of maize in state-certified silos, preventing catastrophic famine or immediate regional supply collapse during the first quarter.
                  </p>
                </div>
              </div>

              <div className="finding-item">
                <div className="finding-num">04</div>
                <div className="finding-content">
                  <h3 className="finding-title">Forward Replacement Contracts Surge by +18%</h3>
                  <p className="finding-desc">
                    Commodity exchange telemetry (Exhibit ORV-0038) confirms physical wheat spot contracts for alternative corridor delivery trade at +18% premiums over December 2026 baseline prices.
                  </p>
                </div>
              </div>
            </div>
          </section>

          {/* ── SECTION 3: COUNTRY & SECTOR EXPOSURE ── */}
          <section className="briefing-section">
            <h2 className="section-heading">3. Country & Sector Exposure</h2>
            <p className="section-intro">
              The table below summarizes verified jurisdictional exposure. Defensible exposure ranges are provided only where backed by verified volume and pricing data.
            </p>

            <div className="exposure-table-wrap">
              <table className="exposure-table">
                <thead>
                  <tr>
                    <th>Country / Jurisdiction</th>
                    <th>Affected Sector</th>
                    <th>Exposure Mechanism</th>
                    <th>Arbitrated Impact</th>
                    <th>Judicial Status</th>
                  </tr>
                </thead>
                <tbody>
                  {countryExposures.map((row, idx) => (
                    <tr key={idx}>
                      <td className="cell-country">
                        <strong>{row.country}</strong>
                      </td>
                      <td className="cell-sector">{row.sector}</td>
                      <td className="cell-mechanism">{row.mechanism}</td>
                      <td className="cell-impact">
                        {row.hasRange ? (
                          <span className="impact-amount">{row.impactRange}</span>
                        ) : (
                          <span className="impact-insufficient">
                            <AlertTriangle size={11} />
                            <span>{row.impactRange}</span>
                          </span>
                        )}
                      </td>
                      <td>
                        <span className={`status-badge status-${row.tone}`}>
                          {row.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* ── SECTION 4: NEXT-QUARTER OUTLOOK ── */}
          <section className="briefing-section">
            <h2 className="section-heading">4. Next-Quarter Outlook (Q1 / Q2 2027)</h2>
            <div className="outlook-prose">
              <div className="outlook-card">
                <h3 className="outlook-card-title">Day 45 Strategic Buffer Depletion Threshold</h3>
                <p>
                  While Tolan and regional silos shield against immediate acute disruption, buffer stocks will deplete to critical minimum reserves by Day 45 (approx. 10 March 2027). Procurement authorities must execute sovereign bilateral supply agreements prior to this threshold to avoid a secondary price shock.
                </p>
              </div>

              <div className="outlook-card">
                <h3 className="outlook-card-title">14-Day Overland Rail Fast-Tracking Window</h3>
                <p>
                  The Vethian overland rail corridor can operationally absorb 30–35% of displaced cargo volume. However, activation requires emergency customs fast-tracking protocols to be signed within 14 days to avert structural rail yard bottlenecks.
                </p>
              </div>

              <div className="outlook-card">
                <h3 className="outlook-card-title">Forward Price Hedging & Settlement Risk</h3>
                <p>
                  With spot delivery premiums elevated by +18%, unhedged commercial importers will absorb substantial margin compression in Q2 unless forward delivery options are locked in before current exchange futures expire.
                </p>
              </div>

              <div className="outlook-assumptions-box">
                <span className="assumptions-label">Stated Analytical Assumptions:</span>
                <ul className="assumptions-list">
                  <li>Normal seasonal weather conditions prevail across alternative agricultural growing regions.</li>
                  <li>No secondary border closures or military embargoes are declared along the Vethian border.</li>
                  <li>Existing bilateral exchange rate bands remain stabilized within +/- 3.5%.</li>
                </ul>
              </div>
            </div>
          </section>

          {/* ── UNCERTAINTY & VERIFICATION GAPS ── */}
          <section className="briefing-section briefing-section--uncertainty">
            <div className="uncertainty-header">
              <ShieldAlert size={16} className="uncertainty-icon" />
              <h2 className="section-heading section-heading--uncertainty">
                Uncertainty & Verification Gaps
              </h2>
            </div>
            <p className="uncertainty-intro">
              In accordance with tribunal evidence standards, the following factors could not be definitively verified under the as-of evaluation cutoff and were excluded from positive liability findings:
            </p>
            <div className="uncertainty-cards-grid">
              <div className="uncertainty-item">
                <h3 className="uncertainty-item-title">Unconfirmed Vethian Customs Fast-Tracking</h3>
                <p className="uncertainty-item-desc">
                  While freight rail capacity (30–35%) is documented in industry reports, sovereign customs fast-tracking remains unratified by treaty. Rerouting offset values remain legally contested.
                </p>
              </div>
              <div className="uncertainty-item">
                <h3 className="uncertainty-item-title">Inadmissible Downstream Wire Retractions</h3>
                <p className="uncertainty-item-desc">
                  Early wire reports (WLD-0024) claiming imminent corridor resumption were formally retracted by the editorial desk and conceded as inadmissible Tier-4 hearsay.
                </p>
              </div>
              <div className="uncertainty-item">
                <h3 className="uncertainty-item-title">Unquantified Peripheral Realm Spillover</h3>
                <p className="uncertainty-item-desc">
                  Secondary indirect impacts on downstream economies (Utgard, Valhalla, Alfheim) lack verified contract series prior to 25 January 2027 and were designated as "Insufficient evidence to estimate."
                </p>
              </div>
            </div>
          </section>

          {/* ── SECTION 5: EVIDENCE & SOURCES ── */}
          <section className="briefing-section">
            <h2 className="section-heading">5. Evidence & Sources</h2>
            <p className="section-intro">
              The conclusions above are grounded in verified Runemark trade documents and certified statistical series. Click any exhibit reference below to inspect the original source text.
            </p>

            <div className="citations-ledger-list">
              {citations.map((cite) => (
                <article key={cite.id} className="citation-ledger-item">
                  <div className="citation-item__left">
                    <button
                      className="citation-open-btn"
                      onClick={() => onDocClick(cite.id)}
                      title={`Open original document ${cite.id}`}
                    >
                      <BookOpen size={13} className="citation-btn-icon" />
                      <span>Exhibit {cite.id}</span>
                      <ArrowRight size={11} className="citation-btn-arrow" />
                    </button>
                    <span className="citation-tier">{cite.tier}</span>
                  </div>

                  <div className="citation-item__details">
                    <h3 className="citation-title">{cite.title}</h3>
                    <span className="citation-source-meta">{cite.source} · Pub Date: {cite.date}</span>
                    <p className="citation-relevance">{cite.relevance}</p>
                  </div>
                </article>
              ))}
            </div>

            {/* Neon DB Cryptographic Ledger Stamp */}
            {neonPersisted && (
              <div className="neon-ledger-stamp">
                <Database size={14} className="neon-stamp-icon" />
                <div className="neon-stamp-text">
                  <strong>CRYPTOGRAPHICALLY PERSISTED TO NEON POSTGRESQL LEDGER</strong>
                  <span>Case ID: {displayMeta.trialId || 'CASE-NR-2027-E5'} · Audit Timestamp: 2027-01-25 12:00:00 UTC · Ingestion Hash: SHA-256 Validated</span>
                </div>
              </div>
            )}
          </section>
        </main>

        {/* ── Document Footer ── */}
        <footer className="briefing-doc__footer">
          <div className="briefing-doc__footer-left">
            <span>High Tribunal Judicial Briefing · Nine Realms Intelligence</span>
          </div>

          <div className="briefing-doc__footer-actions">
            <button
              className="footer-btn-secondary"
              onClick={onClose}
            >
              <span>Return to Courtroom Arena</span>
            </button>

            {onNewTrial && (
              <button
                className="footer-btn-primary"
                onClick={() => {
                  onClose()
                  onNewTrial()
                }}
              >
                <span>Initiate New Trial ⚔</span>
              </button>
            )}
          </div>
        </footer>
      </div>
    </div>
  )
}
