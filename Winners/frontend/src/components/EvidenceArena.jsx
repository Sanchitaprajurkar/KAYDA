import React, { useState } from 'react'
import {
  Scale,
  BookOpen,
  ArrowRight,
  TrendingUp,
  Shield,
  Layers,
  MapPin,
  CheckCircle2,
  AlertTriangle,
  Search,
  Globe
} from 'lucide-react'
import RouteMap from './RouteMap'
import SupplyChainImpact from './SupplyChainImpact'
import { EVIDENCE_REGISTRY } from '../data/trialData'
import './EvidenceArena.css'

export default function EvidenceArena({
  query,
  onCiteClick,
  isResearching = false
}) {
  const [activeTab, setActiveTab] = useState('impact') // 'impact' | 'evidence' | 'map'

  // Verified documents from registry for center stage
  const verifiedDocIds = ['ORV-0017', 'ORV-0023', 'ORV-0031', 'ORV-0044', 'ORV-0038']
  const verifiedDocs = verifiedDocIds.map((id) => EVIDENCE_REGISTRY[id]).filter(Boolean)

  const tradeMetrics = [
    {
      id: 'orvan-volume',
      label: 'Orvan Corridor Deficit',
      value: '~1.2M MT',
      sub: 'Disrupted bulk cargo volume',
      tone: 'danger'
    },
    {
      id: 'midgard-dep',
      label: 'Midgard Import Reliance',
      value: '54% Wheat',
      sub: '38% Maize via Orvan corridor',
      tone: 'danger'
    },
    {
      id: 'tolan-reserves',
      label: 'Tolan Buffer Insulation',
      value: '68 Days Wheat',
      sub: '45 Days Maize in state reserve',
      tone: 'success'
    },
    {
      id: 'spot-premium',
      label: 'Forward Spot Premium',
      value: '+18% Price Surge',
      sub: 'Secondary corridor repricing',
      tone: 'warning'
    }
  ]

  return (
    <div className="evidence-arena">
      {/* ── Arena Header & Sub-Tabs ── */}
      <div className="evidence-arena__header">
        <div className="evidence-arena__title-group">
          <div className="evidence-arena__emblem">
            <Scale size={15} />
          </div>
          <div>
            <h3 className="evidence-arena__title">Evidence Arena</h3>
            <span className="evidence-arena__subtitle">Shared evidence, verified trade data, and corridor telemetry</span>
          </div>
        </div>

        {/* View Toggle: Supply Chain Impact vs Shared Evidence vs Corridor Map */}
        <div className="evidence-arena__tabs">
          <button
            className={`evidence-arena__tab ${activeTab === 'impact' ? 'active' : ''}`}
            onClick={() => setActiveTab('impact')}
          >
            <Globe size={12} />
            <span>Supply Chain Impact</span>
          </button>
          <button
            className={`evidence-arena__tab ${activeTab === 'evidence' ? 'active' : ''}`}
            onClick={() => setActiveTab('evidence')}
          >
            <BookOpen size={12} />
            <span>Shared Evidence</span>
          </button>
          <button
            className={`evidence-arena__tab ${activeTab === 'map' ? 'active' : ''}`}
            onClick={() => setActiveTab('map')}
          >
            <MapPin size={12} />
            <span>Corridor Map</span>
          </button>
        </div>
      </div>

      {/* ── If in Researching Phase: Calm Informational Banner ── */}
      {isResearching ? (
        <div className="evidence-arena__research-banner animate-fade-in">
          <div className="evidence-arena__research-pulse">
            <Search size={18} className="evidence-arena__research-icon" />
          </div>
          <div className="evidence-arena__research-content">
            <h4 className="evidence-arena__research-title">
              Heimdall is examining trade records and collecting evidence…
            </h4>
            <p className="evidence-arena__research-desc">
              Verifying document authenticity, applying as-of clock constraints, and establishing verified exhibits for the High Bench.
            </p>
          </div>
        </div>
      ) : null}

      {/* ── Main Chamber Body ── */}
      {activeTab === 'impact' && (
        <div className="evidence-arena__body animate-fade-in">
          <SupplyChainImpact query={query} onCiteClick={onCiteClick} />
        </div>
      )}

      {activeTab === 'map' && (
        <div className="evidence-arena__map-wrap animate-fade-in">
          <RouteMap />
        </div>
      )}

      {activeTab === 'evidence' && (
        <div className="evidence-arena__body animate-fade-in">
          {/* Key Trade Data Metrics Grid */}
          <div className="evidence-arena__metrics-grid">
            {tradeMetrics.map((m) => (
              <div key={m.id} className={`trade-metric-card metric-${m.tone}`}>
                <span className="trade-metric-card__label">{m.label}</span>
                <span className="trade-metric-card__value">{m.value}</span>
                <span className="trade-metric-card__sub">{m.sub}</span>
              </div>
            ))}
          </div>

          {/* Verified Source Documents List */}
          <div className="evidence-arena__docs-section">
            <div className="evidence-arena__docs-header">
              <span className="evidence-arena__docs-title">Verified Runemark Documents</span>
              <span className="evidence-arena__docs-hint">Click citation to inspect original text</span>
            </div>

            <div className="evidence-arena__docs-list">
              {verifiedDocs.map((doc) => (
                <article key={doc.id} className="verified-doc-card">
                  <div className="verified-doc-card__top">
                    <span className="verified-doc-card__badge">
                      Tier {doc.reliability} · {doc.source}
                    </span>
                    <span className="verified-doc-card__date">{doc.pubDate}</span>
                  </div>

                  <h5 className="verified-doc-card__title">{doc.title}</h5>
                  <p className="verified-doc-card__snippet">{doc.snippet}</p>

                  <div className="verified-doc-card__footer">
                    <button
                      className="verified-doc-card__cite-btn"
                      onClick={() => onCiteClick(doc.id)}
                      title={`Inspect full document ${doc.id}`}
                    >
                      <BookOpen size={12} className="verified-doc-card__cite-icon" />
                      <span>Exhibit {doc.id}</span>
                      <ArrowRight size={11} className="verified-doc-card__cite-arrow" />
                    </button>

                    <span className="verified-doc-card__status">
                      <CheckCircle2 size={11} />
                      <span>Verified Authenticity</span>
                    </span>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
