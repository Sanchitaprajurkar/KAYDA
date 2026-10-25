import React, { useState } from 'react'
import {
  Globe,
  TrendingDown,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  BookOpen,
  ArrowRight,
  ChevronDown,
  ChevronUp,
  Shield,
  Layers,
  X
} from 'lucide-react'
import './SupplyChainImpact.css'

// Disruption scenario datasets with defensible calculations and insufficient evidence guards
const IMPACT_SCENARIOS = {
  taiwan: [
    {
      country: 'Utgard',
      affectedSector: 'Semiconductor manufacturing',
      expectedImpact: '$140M — $220M production bottleneck',
      hasRange: true,
      confidence: '94% (High)',
      confidenceType: 'high',
      whyAffected: "Utgard's industrial factory economy is deeply dependent on imported microchips and wafer components to feed its consumer goods, automotive controls, and assembly facilities.",
      exposedSectors: ['Sub-micron chip assembly', 'Automotive electronics', 'Consumer electronics'],
      evidenceAssessment: 'Official Runemark country profile (ATL-0001) confirms Utgard relies on imported computer chips with less than 21 days of fab inventory buffer.',
      mitigatingFactors: 'Partial domestic component stockpiles; potential reallocation of secondary consumer assembly lines.',
      sourceDocs: ['ATL-0001']
    },
    {
      country: 'Asgard',
      affectedSector: 'Shipping & advanced re-exports',
      expectedImpact: '$45M — $80M rerouting costs',
      hasRange: true,
      confidence: '89% (High)',
      confidenceType: 'high',
      whyAffected: 'Asgard acts as the primary sovereign logistics and transshipment hub for precision avionics and high-reliability aerospace components.',
      exposedSectors: ['Air-bridge logistics', 'Re-export container terminals', 'Aerospace avionics'],
      evidenceAssessment: 'Tier-1 maritime and aviation manifests indicate 32% of Asgardian high-value air cargo routes originate in Taiwan and East Asian fabs.',
      mitigatingFactors: 'Priority bilateral airlift agreements; rapid activation of multimodal European hub re-routing.',
      sourceDocs: ['ATL-0002']
    },
    {
      country: 'Dorin',
      affectedSector: 'Specialty metals & rare-earth dopants',
      expectedImpact: '18% — 25% export revenue decline',
      hasRange: true,
      confidence: '82% (Medium)',
      confidenceType: 'medium',
      whyAffected: 'Smelting foundries in Dorin produce high-purity gallium and germanium precursor alloys tailored specifically for overseas lithography foundries.',
      exposedSectors: ['High-purity metallics', 'Alloy smelting', 'Mining export revenue'],
      evidenceAssessment: 'Export telemetry establishes direct foundry contractual linkages with overseas fab buyers; sudden halt leaves smelted ingots unabsorbed.',
      mitigatingFactors: 'Diverting raw ingots into domestic strategic mineral reserves; sovereign bridge financing for foundries.',
      sourceDocs: ['ATL-0004']
    },
    {
      country: 'Valhalla',
      affectedSector: 'Rice and metals',
      expectedImpact: 'Insufficient evidence to estimate',
      hasRange: false,
      confidence: '42% (Low)',
      confidenceType: 'low',
      whyAffected: 'Valhalla maintains general trading ties, but Runemark records show no direct contract dependencies or verified bilateral semiconductor delivery agreements.',
      exposedSectors: ['Agricultural staple trading', 'Base metal forging'],
      evidenceAssessment: 'No verified trade series or customs declarations link Valhalla directly to semiconductor component disruption prior to the as-of cutoff date.',
      mitigatingFactors: 'Self-sufficient agricultural buffer; broad diversified trading partners.',
      sourceDocs: ['ATL-0012']
    }
  ],
  orvan: [
    {
      country: 'Midgard',
      affectedSector: 'Agriculture (Wheat & Grain)',
      expectedImpact: '$165M — $290M deficit',
      hasRange: true,
      confidence: '92% (High)',
      confidenceType: 'high',
      whyAffected: 'Midgard sources 54% of its wheat and 38% of its maize directly via the Orvan corridor with zero active replacement contracts for Q1 2027.',
      exposedSectors: ['Flour milling', 'Commercial bakery supply', 'Animal feedstock'],
      evidenceAssessment: 'Midgard Ministry of Trade Q4 2026 dependency matrix (ORV-0023) establishes structural reliance on the suspended corridor.',
      mitigatingFactors: 'Bilateral emergency rationing; fast-tracking Vethian rail link agreements.',
      sourceDocs: ['ORV-0023', 'ORV-0017']
    },
    {
      country: 'Tolan',
      affectedSector: 'Agriculture (Maize & Livestock)',
      expectedImpact: '$55M — $110M (Buffer Insulated)',
      hasRange: true,
      confidence: '88% (High)',
      confidenceType: 'high',
      whyAffected: 'Tolan relies on Orvan for 41% of wheat and 29% of maize, but state strategic reserves absorb the immediate quarterly food-security breach.',
      exposedSectors: ['Livestock farming', 'Feedstock processing'],
      evidenceAssessment: 'Tolan Bureau of Statistics report (ORV-0031) establishes 68 days of wheat and 45 days of maize buffer stocks in certified silos.',
      mitigatingFactors: '68-day buffer absorbs immediate Q1 shock; strategic reserve drawdown schedule shields consumer pricing.',
      sourceDocs: ['ORV-0031']
    },
    {
      country: 'Vethi',
      affectedSector: 'Overland Rail Logistics',
      expectedImpact: '-$65M — -$90M (Volume Offset)',
      hasRange: true,
      confidence: '68% (Medium)',
      confidenceType: 'medium',
      whyAffected: 'Vethian overland corridor can absorb 30–35% of displaced Orvan grain volume if customs fast-tracking is ratified.',
      exposedSectors: ['Rail freight', 'Cross-border customs logistics'],
      evidenceAssessment: 'Runemark Freight Exchange report (ORV-0044) confirms physical rail capacity with an 8–12 day activation lead time.',
      mitigatingFactors: 'Customs fast-track fast-tracked under regional emergency transport decree.',
      sourceDocs: ['ORV-0044']
    },
    {
      country: 'Alfheim',
      affectedSector: 'Specialty chemicals & fertilizer',
      expectedImpact: 'Insufficient evidence to estimate',
      hasRange: false,
      confidence: '35% (Low)',
      confidenceType: 'low',
      whyAffected: 'Alfheim supplies secondary agricultural chemicals, but Runemark trade filings do not document specific disrupted contract quantities.',
      exposedSectors: ['Agrochemical synthesis', 'Fertilizer distribution'],
      evidenceAssessment: 'Corpus lacks verified volume series linking Alfheim agrochemical lines directly to Orvan corridor suspension.',
      mitigatingFactors: 'Flexible maritime routing through unblocked southern routes.',
      sourceDocs: ['ATL-0011']
    }
  ],
  suez: [
    {
      country: 'Asgard',
      affectedSector: 'Deepwater container freight',
      expectedImpact: '$80M — $135M delay costs',
      hasRange: true,
      confidence: '91% (High)',
      confidenceType: 'high',
      whyAffected: 'Maritime container vessels rerouted around the Cape corridor add 12–16 days of transit latency and elevate bunker fuel expenditure.',
      exposedSectors: ['Container line operations', 'Port terminal congestion'],
      evidenceAssessment: 'Verified AIS vessel telemetry and freight rate indexes confirm route diversion and demurrage surcharges.',
      mitigatingFactors: 'Slow-steaming fuel conservation; container inventory visibility systems.',
      sourceDocs: ['ATL-0002']
    },
    {
      country: 'Midgard',
      affectedSector: 'Automotive & industrial assembly',
      expectedImpact: '$60M — $95M component delays',
      hasRange: true,
      confidence: '86% (High)',
      confidenceType: 'high',
      whyAffected: 'Automotive assembly plants operate on just-in-time logistics with parts stranded in congested transit lanes.',
      exposedSectors: ['Vehicle assembly', 'Heavy machinery'],
      evidenceAssessment: 'Import manifests indicate 40% of sub-tier automotive assemblies traverse the affected corridor.',
      mitigatingFactors: 'Switching critical components to expedited air freight.',
      sourceDocs: ['ATL-0001']
    },
    {
      country: 'Muspelheim',
      affectedSector: 'Bunker fuel & petrochemicals',
      expectedImpact: '+22% freight rate escalation',
      hasRange: true,
      confidence: '88% (High)',
      confidenceType: 'high',
      whyAffected: 'Elevated transit distances increase marine fuel consumption, spiking refinery spot prices across regional terminals.',
      exposedSectors: ['Petrochemical refining', 'Bunker fuel supply'],
      evidenceAssessment: 'Exchange spot commodity indexes record immediate +22% premium on maritime heavy fuel contracts.',
      mitigatingFactors: 'Releasing regional fuel reserves to stabilize spot pricing.',
      sourceDocs: ['ATL-0014']
    },
    {
      country: 'Jotunheim',
      affectedSector: 'Arctic Northern Sea lane',
      expectedImpact: 'Insufficient evidence to estimate',
      hasRange: false,
      confidence: '38% (Low)',
      confidenceType: 'low',
      whyAffected: 'Seasonal ice constraints prevent immediate commercial rerouting along the northern route without icebreaker escorts.',
      exposedSectors: ['Arctic maritime shipping', 'Cold-chain logistics'],
      evidenceAssessment: 'No verified commercial transit charters approved for general container freight as of January 2027.',
      mitigatingFactors: 'Long-term icebreaker infrastructure planning.',
      sourceDocs: ['ATL-0015']
    }
  ]
}

export default function SupplyChainImpact({
  query = '',
  onCiteClick
}) {
  const [selectedCountry, setSelectedCountry] = useState(null)

  // Dynamically detect scenario based on user query
  let scenarioKey = 'taiwan'
  const qLower = (query || '').toLowerCase()
  if (qLower.includes('orvan') || qLower.includes('grain') || qLower.includes('wheat') || qLower.includes('maize')) {
    scenarioKey = 'orvan'
  } else if (qLower.includes('suez') || qLower.includes('red sea') || qLower.includes('shipping') || qLower.includes('maritime')) {
    scenarioKey = 'suez'
  }

  const rows = IMPACT_SCENARIOS[scenarioKey] || IMPACT_SCENARIOS.taiwan
  const activeDetail = selectedCountry ? rows.find((r) => r.country === selectedCountry) : null

  return (
    <div className="impact-summary-panel">
      {/* ── Table Header ── */}
      <div className="impact-summary__header">
        <div className="impact-summary__title-group">
          <Globe size={16} className="impact-summary__globe-icon" />
          <h4 className="impact-summary__title">🌍 Supply Chain Impact</h4>
        </div>
        <span className="impact-summary__hint">Click a country to inspect evidence & mitigating factors</span>
      </div>

      {/* ── Impact Table ── */}
      <div className="impact-summary__table-wrap">
        <table className="impact-summary__table">
          <thead>
            <tr>
              <th className="th-country">Country</th>
              <th className="th-sector">Affected Sector</th>
              <th className="th-impact">Expected Impact</th>
              <th className="th-confidence">Confidence</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const isSelected = selectedCountry === row.country
              return (
                <tr
                  key={row.country}
                  className={`impact-row ${isSelected ? 'row-active' : ''}`}
                  onClick={() => setSelectedCountry(isSelected ? null : row.country)}
                  tabIndex={0}
                  role="button"
                  aria-expanded={isSelected}
                >
                  <td className="td-country">
                    <div className="country-cell">
                      <span className="country-name">{row.country}</span>
                      {isSelected ? <ChevronUp size={12} className="chevron-icon" /> : <ChevronDown size={12} className="chevron-icon" />}
                    </div>
                  </td>
                  <td className="td-sector">
                    <span className="sector-text">{row.affectedSector}</span>
                  </td>
                  <td className="td-impact">
                    {row.hasRange ? (
                      <span className="impact-val impact-val--range">{row.expectedImpact}</span>
                    ) : (
                      <span className="impact-val impact-val--insufficient">
                        <AlertTriangle size={11} className="insufficient-icon" />
                        <span>Insufficient evidence to estimate</span>
                      </span>
                    )}
                  </td>
                  <td className="td-confidence">
                    <span className={`confidence-pill pill-${row.confidenceType}`}>
                      {row.confidence}
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* ── Country Deep-Dive Drawer / Detail Card (When row is clicked) ── */}
      {activeDetail && (
        <div className="country-detail-drawer animate-fade-in">
          <div className="country-detail__header">
            <div className="country-detail__title-row">
              <span className="country-detail__badge">Country Profile Deep-Dive</span>
              <h5 className="country-detail__name">{activeDetail.country} — Supply Chain Impact Analysis</h5>
            </div>
            <button
              className="country-detail__close-btn"
              onClick={() => setSelectedCountry(null)}
              aria-label="Close detail"
            >
              <X size={14} />
            </button>
          </div>

          <div className="country-detail__grid">
            {/* 1. Why it is affected */}
            <div className="country-detail__block">
              <span className="detail-block__label">Why It Is Affected</span>
              <p className="detail-block__text">{activeDetail.whyAffected}</p>
            </div>

            {/* 2. Which sectors are exposed */}
            <div className="country-detail__block">
              <span className="detail-block__label">Exposed Sectors</span>
              <div className="detail-block__tags">
                {activeDetail.exposedSectors.map((sec, i) => (
                  <span key={i} className="sector-tag">{sec}</span>
                ))}
              </div>
            </div>

            {/* 3. Evidence supporting assessment */}
            <div className="country-detail__block">
              <span className="detail-block__label">Supporting Judicial Evidence</span>
              <p className="detail-block__text">{activeDetail.evidenceAssessment}</p>
            </div>

            {/* 4. Potential mitigating factors */}
            <div className="country-detail__block">
              <span className="detail-block__label">Potential Mitigating Factors</span>
              <p className="detail-block__text detail-block__text--mitigation">
                <Shield size={12} className="mitigation-icon" />
                <span>{activeDetail.mitigatingFactors}</span>
              </p>
            </div>
          </div>

          {/* 5. Relevant source documents */}
          <div className="country-detail__footer">
            <span className="detail-footer__label">Relevant Source Exhibits:</span>
            <div className="detail-footer__docs">
              {activeDetail.sourceDocs.map((docId) => (
                <button
                  key={docId}
                  className="detail-doc-btn"
                  onClick={() => onCiteClick(docId)}
                  title={`Inspect original Runemark document ${docId}`}
                >
                  <BookOpen size={12} className="detail-doc-icon" />
                  <span>Exhibit {docId}</span>
                  <ArrowRight size={11} className="detail-doc-arrow" />
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
