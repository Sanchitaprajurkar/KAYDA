import React, { useState } from 'react'
import {
  Shield,
  Zap,
  Eye,
  Scale,
  ArrowRight,
  Activity,
  Compass,
  CheckCircle2,
  FileCheck,
  Radio,
  ExternalLink,
  ChevronRight,
  Menu,
  X,
  Layers,
  Globe
} from 'lucide-react'
import './Homepage.css'

export default function Homepage({ onEnterArena }) {
  const [activeRealm, setActiveRealm] = useState('asgard')
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const realms = [
    {
      id: 'asgard',
      name: 'ASGARD',
      role: 'Tier-1 Sovereign Command Hub',
      rune: 'ᚬ',
      status: 'OPTIMAL',
      statusType: 'optimal',
      desc: 'Central coordination nexus for enterprise assembly, supply-chain orchestration, and supreme contractual authority.',
      riskScore: '12%',
      corridor: 'Orbital North-Euro Spine',
      activeShipments: 1420
    },
    {
      id: 'midgard',
      name: 'MIDGARD',
      role: 'Terrestrial Freight & Mega-Ports',
      rune: 'ᛗ',
      status: 'HIGH ALERT',
      statusType: 'alert',
      desc: 'Primary maritime shipping routes, deepwater container terminals, and congested chokepoints along global straits.',
      riskScore: '78%',
      corridor: 'Malacca Strait / Rotterdam',
      activeShipments: 3890
    },
    {
      id: 'alfheim',
      name: 'ALFHEIM',
      role: 'Photonics & Advanced Semiconductor Fab',
      rune: 'ᚨ',
      status: 'SCRUTINY',
      statusType: 'scrutiny',
      desc: 'Sub-micron optical lithography, wafer fabrication, and zero-defect clean-room component logistics.',
      riskScore: '41%',
      corridor: 'Taipei-Incheon Silicon Air Bridge',
      activeShipments: 640
    },
    {
      id: 'nidavellir',
      name: 'NIDAVELLIR',
      role: 'Nano-Foundries & Heavy Forges',
      rune: 'ᚾ',
      status: 'OPTIMAL',
      statusType: 'optimal',
      desc: 'Automated smelting facilities, structural titanium fabrication, and critical precision alloy casting.',
      riskScore: '19%',
      corridor: 'Ruhr Industrial Corridor',
      activeShipments: 810
    },
    {
      id: 'jotunheim',
      name: 'JOTUNHEIM',
      role: 'Sub-Zero Cold Chain & Arctic Freight',
      rune: 'ᛁ',
      status: 'HIGH ALERT',
      statusType: 'alert',
      desc: 'Deep-freeze cryogenic storage, pharmaceutical cold-chain lines, and northern sea-route icebreaker paths.',
      riskScore: '84%',
      corridor: 'Barents Sea / Northern Sea Lane',
      activeShipments: 412
    },
    {
      id: 'muspelheim',
      name: 'MUSPELHEIM',
      role: 'Thermal Power & High-Yield Refineries',
      rune: 'ᛏ',
      status: 'OPTIMAL',
      statusType: 'optimal',
      desc: 'Petrochemical liquefaction, geothermal power generation, and synthetic fuel supply depots.',
      riskScore: '26%',
      corridor: 'Strait of Hormuz Petro-Grid',
      activeShipments: 1190
    },
    {
      id: 'vanaheim',
      name: 'VANAHEIM',
      role: 'Agro-Biotech & Sustenance Logistics',
      rune: 'ᚹ',
      status: 'OPTIMAL',
      statusType: 'optimal',
      desc: 'Synthetic proteins, climate-controlled grain silos, and continuous bio-fuel replenishment corridors.',
      riskScore: '15%',
      corridor: 'Pan-American Grain Line',
      activeShipments: 950
    },
    {
      id: 'svartalfheim',
      name: 'SVARTALFHEIM',
      role: 'Subterranean Rare-Earth Extraction',
      rune: 'ᛋ',
      status: 'SCRUTINY',
      statusType: 'scrutiny',
      desc: 'Deep-shaft neodymium and dysprosium mining, lithium refinement, and raw precursor processing.',
      riskScore: '53%',
      corridor: 'Atacama-Congo Raw Freight',
      activeShipments: 520
    },
    {
      id: 'helheim',
      name: 'HELHEIM',
      role: 'Default Liquidation & Deadlock Salvage',
      rune: 'ᚺ',
      status: 'SCRUTINY',
      statusType: 'scrutiny',
      desc: 'Insolvency mitigation, distressed asset buyouts, scrap titanium reclamation, and insurance escrow liquidation.',
      riskScore: '67%',
      corridor: 'Alang-Chittagong Scrapping Yards',
      activeShipments: 195
    }
  ]

  const tribunalAgents = [
    {
      id: 'heimdall',
      name: 'HEIMDALL',
      title: 'The All-Seeing Sentinel',
      role: 'Data Ingestion & Signal Detection',
      icon: <Eye size={28} />,
      accentClass: 'hp-agent-heimdall',
      color: '#00D4FF',
      desc: 'Monitors over 14,000 multi-modal freight arteries in real-time. Ingests satellite AIS transponder logs, bills of lading, and port gate queues before anomalies manifest.',
      stance: '“No anomaly slips through the Bifrost. The evidence is seen before the storm breaks.”',
      telemetry: '14,280 FEEDS/SEC'
    },
    {
      id: 'thor',
      name: 'THOR',
      title: 'The Storm Defender',
      role: 'Risk Continuity & Defense Proponent',
      icon: <Zap size={28} />,
      accentClass: 'hp-agent-thor',
      color: '#E63946',
      desc: 'Upholds supplier commitments and operational continuity under extreme duress. Aggressively proposes rerouting buffers, stress-tests emergency alternatives, and defends fulfillment.',
      stance: '“Force majeure is not an excuse for surrender. The cargo moves, or we forge new paths.”',
      telemetry: '94.2% RESILIENCE SCORE'
    },
    {
      id: 'loki',
      name: 'LOKI',
      title: 'The Trickster Arbiter',
      role: 'Adversarial Risk & Fraud Skeptic',
      icon: <Shield size={28} />,
      accentClass: 'hp-agent-loki',
      color: '#00C878',
      desc: 'Ruthlessly cross-examines every invoice, carrier excuse, and phantom inventory report. Isolates hidden sanction vulnerabilities and predicts secondary systemic defaults.',
      stance: '“Everyone lies when the ship sinks. Show me the cryptographic fuel logs or forfeit the bond.”',
      telemetry: '88.7% VULNERABILITY CULL'
    },
    {
      id: 'odin',
      name: 'ODIN',
      title: 'The Allfather Justice',
      role: 'Supreme Bench & Binding Verdict Engine',
      icon: <Scale size={28} />,
      accentClass: 'hp-agent-odin',
      color: '#D7B56D',
      desc: 'Weighs Thor’s claims against Loki’s forensic rebuttals through deterministic mathematical synthesis. Issues unappealable multi-signature verdicts and automated escrow releases.',
      stance: '“The scales do not yield to rhetoric. Only verified telemetry commands the Allfather’s seal.”',
      telemetry: '<1.4s MULTI-SIG FINALITY'
    }
  ]

  const workflowSteps = [
    {
      step: '01',
      title: 'DISCOVER',
      actor: 'Heimdall Sentinel',
      numClass: 'step-1',
      desc: 'Automated satellite and IoT feeds detect sudden port choke points, typhoon deviations, or customs clearance halts.'
    },
    {
      step: '02',
      title: 'INVESTIGATE',
      actor: 'Telemetry Ingestion',
      numClass: 'step-2',
      desc: 'Digital bills of lading, AIS waypoints, and container telemetry are cryptographically timestamped and indexed on-chain.'
    },
    {
      step: '03',
      title: 'DEBATE',
      actor: 'Thor vs. Loki Arena',
      numClass: 'step-3',
      desc: 'Adversarial AI agents cross-examine claims and counter-claims, stripping out hallucinations and isolating unverified assertions.'
    },
    {
      step: '04',
      title: 'VERDICT',
      actor: 'Odin Allfather Bench',
      numClass: 'step-4',
      desc: 'Deterministic judgment assigns contractual liability, triggers insurance escrows, and recalculates global exposure in real-time.'
    }
  ]

  const scrollToSection = (e, id) => {
    e.preventDefault()
    setMobileMenuOpen(false)
    const element = document.getElementById(id)
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' })
    }
  }

  return (
    <div className="hp-wrap">
      {/* Background Ambience & Runic Grid */}
      <div className="hp-atmosphere" />
      <div className="hp-runic-grid" />

      {/* ── Top Navigation Bar ── */}
      <nav className="hp-nav">
        <a href="#hero" className="hp-brand" onClick={(e) => scrollToSection(e, 'hero')}>
          <div className="hp-brand-icon">⚔</div>
          <div className="hp-brand-text">
            NINE REALMS
            <span className="hp-brand-tag">AI ARBITRATION</span>
          </div>
        </a>

        <ul className="hp-nav-links">
          <li><a href="#realms" onClick={(e) => scrollToSection(e, 'realms')}>The Nine Realms</a></li>
          <li><a href="#tribunal" onClick={(e) => scrollToSection(e, 'tribunal')}>The Tribunal</a></li>
          <li><a href="#workflow" onClick={(e) => scrollToSection(e, 'workflow')}>How It Works</a></li>
          <li><a href="#arena-preview" onClick={(e) => scrollToSection(e, 'arena-preview')}>Trial Arena</a></li>
          <li><a href="#intelligence" onClick={(e) => scrollToSection(e, 'intelligence')}>Intelligence</a></li>
        </ul>

        <div className="hp-nav-actions">
          <div className="hp-nav-status">
            <span className="hp-status-dot" />
            <span>BIFROST FEED ACTIVE</span>
          </div>
          <button className="hp-btn-nav" onClick={onEnterArena}>
            <span>ENTER TRIAL ARENA</span>
            <ArrowRight size={14} />
          </button>
          <button 
            className="hp-hamburger" 
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle Menu"
          >
            {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>
      </nav>

      {/* Mobile Menu Dropdown */}
      {mobileMenuOpen && (
        <div style={{
          position: 'fixed',
          top: 68,
          left: 0,
          right: 0,
          background: 'rgba(8, 10, 10, 0.98)',
          borderBottom: '1px solid var(--border-hi)',
          padding: '1.5rem',
          zIndex: 99,
          display: 'flex',
          flexDirection: 'column',
          gap: '1rem'
        }}>
          <a href="#realms" onClick={(e) => scrollToSection(e, 'realms')} style={{ color: '#fff', textDecoration: 'none', padding: '0.5rem 0' }}>The Nine Realms</a>
          <a href="#tribunal" onClick={(e) => scrollToSection(e, 'tribunal')} style={{ color: '#fff', textDecoration: 'none', padding: '0.5rem 0' }}>The Tribunal</a>
          <a href="#workflow" onClick={(e) => scrollToSection(e, 'workflow')} style={{ color: '#fff', textDecoration: 'none', padding: '0.5rem 0' }}>How It Works</a>
          <a href="#arena-preview" onClick={(e) => scrollToSection(e, 'arena-preview')} style={{ color: '#fff', textDecoration: 'none', padding: '0.5rem 0' }}>Trial Arena</a>
          <a href="#intelligence" onClick={(e) => scrollToSection(e, 'intelligence')} style={{ color: '#fff', textDecoration: 'none', padding: '0.5rem 0' }}>Intelligence</a>
          <button className="hp-btn-nav" onClick={() => { setMobileMenuOpen(false); onEnterArena(); }} style={{ width: '100%', justifyContent: 'center' }}>
            ENTER TRIAL ARENA →
          </button>
        </div>
      )}

      {/* ── 1. Hero Section: The First Impression ── */}
      <section id="hero" className="hp-hero">
        <div className="hp-hero-grid">
          {/* Left Side: Copy & CTA */}
          <div className="hp-hero-left">
            <div className="hp-hero-badge">
              <span className="hp-badge-rune">⚔</span>
              <span>THE AGE OF INTELLIGENT ARBITRATION</span>
            </div>

            <h1 className="hp-hero-title">
              EVERY REALM HAS A STORY.
              <span className="hp-hero-title-accent">EVERY STORY FACES TRIAL.</span>
            </h1>

            <p className="hp-hero-desc">
              When international supply chains fracture under conflict, sanctions, and maritime bottlenecks, subjective claims collapse. 
              The Nine Realms Tribunal deploys adversarial multi-agent courtroom intelligence to cross-examine facts, verify cryptographic telemetry, and render deterministic verdicts in seconds.
            </p>

            <div className="hp-hero-actions">
              <button 
                className="hp-btn-primary" 
                onClick={onEnterArena}
              >
                <span>ENTER THE REALMS</span>
                <ArrowRight size={17} />
              </button>

              <button 
                className="hp-btn-secondary" 
                onClick={onEnterArena}
              >
                <span>EXPLORE THE TRIAL</span>
                <ExternalLink size={16} />
              </button>
            </div>

            {/* Micro Indicators */}
            <div className="hp-hero-indicators">
              <div className="hp-indicator-item">
                <span className="hp-indicator-val thor-c">4 AGENTS</span>
                <span className="hp-indicator-label">Adversarial Courtroom AI</span>
              </div>
              <div className="hp-indicator-item">
                <span className="hp-indicator-val loki-c">100%</span>
                <span className="hp-indicator-label">Cryptographic Telemetry Proof</span>
              </div>
              <div className="hp-indicator-item">
                <span className="hp-indicator-val odin-c">&lt;1.4s</span>
                <span className="hp-indicator-label">Deterministic Ruling Finality</span>
              </div>
            </div>
          </div>

          {/* Right Side: Thor & Loki Visual */}
          <div className="hp-hero-right">
            <div className="hp-hero-stage">
              {/* Backlight Atmosphere behind Thor (Crimson) and Loki (Emerald) */}
              <div className="hp-stage-glow-thor" />
              <div className="hp-stage-glow-loki" />
              <div className="hp-stage-runic-halo" />

              {/* The Hero Image Container with thor.jpg */}
              <div className="hp-hero-img-box">
                <img 
                  src="/thor.jpg" 
                  alt="Thor and Loki — Adversarial AI Tribunal Champions" 
                  className="hp-hero-img"
                />

                {/* Blending gradients into dark background */}
                <div className="hp-img-fade-bottom" />
                <div className="hp-img-fade-left" />
                <div className="hp-img-fade-right" />
                <div className="hp-img-fade-top" />
              </div>

              {/* Floating Agent Badge: Thor (Defender) */}
              <div className="hp-floating-chip hp-chip-thor">
                <div className="hp-chip-header">
                  <Zap size={14} />
                  <span>THOR // DEFENDER</span>
                </div>
                <div className="hp-chip-sub">Fulfillment & Resilience Advocate</div>
                <span className="hp-chip-badge">PROSECUTION BENCH</span>
              </div>

              {/* Floating Agent Badge: Loki (Skeptic) */}
              <div className="hp-floating-chip hp-chip-loki">
                <div className="hp-chip-header">
                  <span>LOKI // ARBITER</span>
                  <Shield size={14} />
                </div>
                <div className="hp-chip-sub">Fraud & Hidden Exposure Skeptic</div>
                <span className="hp-chip-badge">CONTRARIAN AUDIT</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── 2. The Nine Realms Section ── */}
      <section id="realms" className="hp-section">
        <div className="hp-section-header">
          <div className="hp-section-tag">
            <Globe size={13} />
            <span>INTERCONNECTED SUPPLY CHAINS</span>
          </div>
          <h2 className="hp-section-title">THE NINE REALMS</h2>
          <p className="hp-section-subtitle">
            Global trade is an intricate mythological tree of dependencies. A freeze in Jotunheim or a blast in Muspelheim cascades immediately across all sovereign nodes.
          </p>
        </div>

        <div className="hp-realms-grid">
          {realms.map((realm) => (
            <div 
              key={realm.id}
              className={`hp-realm-card ${activeRealm === realm.id ? 'active' : ''}`}
              onClick={() => setActiveRealm(realm.id)}
            >
              <div className="hp-realm-top">
                <div className="hp-realm-rune">{realm.rune}</div>
                <div className={`hp-realm-status status-${realm.statusType}`}>
                  {realm.status}
                </div>
              </div>

              <h3 className="hp-realm-name">{realm.name}</h3>
              <div className="hp-realm-role">{realm.role}</div>
              <p className="hp-realm-desc">{realm.desc}</p>

              <div className="hp-realm-telemetry">
                <span>RISK: <strong>{realm.riskScore}</strong></span>
                <span>CORRIDOR: <strong>{realm.corridor}</strong></span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── 3. Meet the Tribunal (4 Agents) ── */}
      <section id="tribunal" className="hp-section">
        <div className="hp-section-header">
          <div className="hp-section-tag">
            <Scale size={13} />
            <span>THE ADVERSARIAL MAGISTRACY</span>
          </div>
          <h2 className="hp-section-title">MEET THE TRIBUNAL</h2>
          <p className="hp-section-subtitle">
            Truth is never revealed by a solitary voice. Four specialized autonomous intelligences probe, cross-examine, and balance the scales of global commerce.
          </p>
        </div>

        <div className="hp-tribunal-grid">
          {tribunalAgents.map((agent) => (
            <div key={agent.id} className={`hp-agent-card ${agent.accentClass}`}>
              <div className="hp-agent-avatar">
                {agent.icon}
              </div>
              <h3 className="hp-agent-title">{agent.name}</h3>
              <div className="hp-agent-archetype">{agent.title}</div>
              <p className="hp-agent-desc">{agent.desc}</p>

              <div className="hp-agent-stance">
                <div className="hp-agent-stance-lbl">Mandate Stance</div>
                <div className="hp-agent-stance-text">{agent.stance}</div>
              </div>

              <div className="hp-agent-metric">
                <span>CORE TELEMETRY</span>
                <span style={{ color: agent.color, fontWeight: 600 }}>{agent.telemetry}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── 4. How It Works (Workflow) ── */}
      <section id="workflow" className="hp-section">
        <div className="hp-section-header">
          <div className="hp-section-tag">
            <Layers size={13} />
            <span>DETERMINISTIC LITIGATION CYCLE</span>
          </div>
          <h2 className="hp-section-title">HOW IT WORKS</h2>
          <p className="hp-section-subtitle">
            From sensor-level signal detection to final multi-signature escrow release: the Four-Step Trial Protocol.
          </p>
        </div>

        <div className="hp-workflow-steps">
          <div className="hp-workflow-line" />
          {workflowSteps.map((step) => (
            <div key={step.step} className={`hp-step-card ${step.numClass}`}>
              <div className="hp-step-num">{step.step}</div>
              <h4 className="hp-step-title">{step.title}</h4>
              <div className="hp-step-actor">{step.actor}</div>
              <p className="hp-step-desc">{step.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── 5. The Trial Arena Preview ── */}
      <section id="arena-preview" className="hp-section">
        <div className="hp-section-header">
          <div className="hp-section-tag">
            <Radio size={13} />
            <span>LIVE COURTROOM TELEMETRY</span>
          </div>
          <h2 className="hp-section-title">THE TRIAL ARENA</h2>
          <p className="hp-section-subtitle">
            Witness Thor and Loki debate live evidence in real time while Odin synthesizes the final legal judgment.
          </p>
        </div>

        <div className="hp-arena-preview-box">
          <div className="hp-arena-bar">
            <div className="hp-arena-case">
              <span className="hp-status-dot" />
              <span>ARBITRATION CASE #TR-2026-904: SUEZ & MALACCA STRAIT BOTTLENECK</span>
            </div>
            <div style={{ color: 'var(--odin-hi)' }}>STATUS: ROUND 03 / CROSS-EXAMINATION</div>
          </div>

          <div className="hp-arena-body">
            {/* Thor Side */}
            <div className="hp-preview-column hp-preview-thor">
              <div className="hp-preview-hdr">
                <h4>⚡ THOR · PROSECUTION ARGUMENT</h4>
                <span className="hp-cite-pill" style={{ color: 'var(--thor-hi)' }}>CONFIDENCE 94%</span>
              </div>
              <div className="hp-preview-claim">
                <div className="hp-claim-header">
                  <span>CLAIM #TH-01 // REROUTE FEASIBILITY</span>
                  <span style={{ color: 'var(--thor-hi)' }}>VERIFIED VIA SATELLITE</span>
                </div>
                <div className="hp-claim-title">
                  Carrier diverted via Cape of Good Hope with compliant bunker reserves.
                </div>
                <div className="hp-claim-reason">
                  AIS telematics confirm vessel MV Odin-Nordic altered course at 03:14 UTC. Total fuel delta falls well within Tier-1 force majeure reserve tolerances.
                </div>
                <div className="hp-claim-citations">
                  <span className="hp-cite-pill">AIS-SAT-9022</span>
                  <span className="hp-cite-pill">FUEL-LOG-78</span>
                  <span className="hp-cite-pill">MARITIME-EXCUSE-4B</span>
                </div>
              </div>
            </div>

            {/* Loki Side */}
            <div className="hp-preview-column hp-preview-loki">
              <div className="hp-preview-hdr">
                <h4>🐍 LOKI · CONTRARIAN REBUTTAL</h4>
                <span className="hp-cite-pill" style={{ color: 'var(--loki-hi)' }}>EXPOSURE 86%</span>
              </div>
              <div className="hp-preview-claim">
                <div className="hp-claim-header">
                  <span>REBUTTAL #LK-01 // PHANTOM INVENTORY</span>
                  <span style={{ color: 'var(--loki-hi)' }}>SANCTION EXPOSURE DETECTED</span>
                </div>
                <div className="hp-claim-title">
                  Bills of lading conceal secondary transshipment through unverified port.
                </div>
                <div className="hp-claim-reason">
                  Customs declaration hash mismatch on container lot #C-4412. Intermediate customs broker in Helheim terminal was sanctioned 48 hours prior to cargo handoff.
                </div>
                <div className="hp-claim-citations">
                  <span className="hp-cite-pill">CUSTOMS-ERR-91</span>
                  <span className="hp-cite-pill">OFAC-REG-2026</span>
                  <span className="hp-cite-pill">HASH-MISMATCH</span>
                </div>
              </div>
            </div>
          </div>

          {/* Odin's Verdict Preview Bar */}
          <div className="hp-arena-bottom-banner">
            <div className="hp-odin-verdict-preview">
              <div className="hp-odin-icon">⚖</div>
              <div className="hp-odin-verdict-text">
                <strong>ODIN'S PRELIMINARY RULING:</strong> Fuel surcharge upheld ($410k), penalty mitigation applied to Loki's sanction discovery. Net exposure: $1.2M.
              </div>
            </div>
            <button className="hp-btn-primary" onClick={onEnterArena}>
              <span>ENTER FULL TRIAL ARENA</span>
              <ArrowRight size={16} />
            </button>
          </div>
        </div>
      </section>

      {/* ── 6. Intelligence, Not Guesswork ── */}
      <section id="intelligence" className="hp-section">
        <div className="hp-section-header">
          <div className="hp-section-tag">
            <CheckCircle2 size={13} />
            <span>THE EVIDENCE ENGINE</span>
          </div>
          <h2 className="hp-section-title">INTELLIGENCE, NOT GUESSWORK</h2>
          <p className="hp-section-subtitle">
            Eliminating LLM hallucinations through cryptographic document hashing, AIS telemetry validation, and dual-agent adversarial stress-testing.
          </p>
        </div>

        <div className="hp-intel-grid">
          <div className="hp-intel-features">
            <div className="hp-feature-card">
              <div className="hp-feature-icon"><FileCheck size={22} /></div>
              <div className="hp-feature-content">
                <h4>Cryptographic Document Proof</h4>
                <p>Every commercial invoice, bill of lading, and port clearance log is SHA-256 hashed at ingestion, preventing post-facto contract tampering.</p>
              </div>
            </div>

            <div className="hp-feature-card">
              <div className="hp-feature-icon"><Compass size={22} /></div>
              <div className="hp-feature-content">
                <h4>Satellite AIS Ingestion</h4>
                <p>Live satellite constellation feeds continuously cross-reference vessel locations, draft heights, and maritime transponders in real-time.</p>
              </div>
            </div>

            <div className="hp-feature-card">
              <div className="hp-feature-icon"><Shield size={22} /></div>
              <div className="hp-feature-content">
                <h4>Adversarial Game-Theoretic Debate</h4>
                <p>By pitting Thor and Loki against each other, the system automatically checks every vulnerability before a single dollar moves.</p>
              </div>
            </div>
          </div>

          <div className="hp-intel-metric-box">
            <div className="hp-metric-header">
              <span className="hp-cinzel" style={{ fontSize: '1.1rem', color: '#fff', fontWeight: 700 }}>VERIFICATION AUDIT TELEMETRY</span>
              <span className="hp-cite-pill" style={{ color: 'var(--odin-hi)' }}>LIVE RUNTIME</span>
            </div>

            <div className="hp-metric-row">
              <span className="hp-metric-label">Document Tamper Resistance</span>
              <span className="hp-metric-value" style={{ color: 'var(--loki-hi)' }}>100.0% SHA-256</span>
            </div>
            <div className="hp-metric-row">
              <span className="hp-metric-label">Satellite Ephemeris Sync</span>
              <span className="hp-metric-value" style={{ color: 'var(--heimdall)' }}>&lt; 380ms Latency</span>
            </div>
            <div className="hp-metric-row">
              <span className="hp-metric-label">Cross-Realm Chokepoint Alerts</span>
              <span className="hp-metric-value" style={{ color: 'var(--thor-hi)' }}>4 Active Signals</span>
            </div>
            <div className="hp-metric-row">
              <span className="hp-metric-label">Hallucination Mitigation Protocol</span>
              <span className="hp-metric-value" style={{ color: 'var(--odin-hi)' }}>Dual-Adversarial Enforced</span>
            </div>
            <div className="hp-metric-row">
              <span className="hp-metric-label">Smart-Contract Escrow Finality</span>
              <span className="hp-metric-value">Deterministic Multi-Sig</span>
            </div>
          </div>
        </div>
      </section>

      {/* ── 7. Final CTA: The Realms Await ── */}
      <section className="hp-cta-section">
        <div className="hp-cta-box">
          <div className="hp-cta-glow" />
          <h2 className="hp-cta-title">THE REALMS AWAIT THEIR VERDICT</h2>
          <p className="hp-cta-subtitle">
            Step onto the Bifrost bridge. Experience autonomous adversarial AI arbitration engineered for the highest-stakes global supply chains.
          </p>

          <div className="hp-cta-actions">
            <button className="hp-btn-primary" onClick={onEnterArena}>
              <span>ENTER THE TRIAL ARENA</span>
              <ArrowRight size={18} />
            </button>
            <button className="hp-btn-secondary" onClick={(e) => scrollToSection(e, 'realms')}>
              <span>INSPECT THE NINE REALMS</span>
              <ChevronRight size={18} />
            </button>
          </div>
        </div>
      </section>

      {/* ── 8. Footer ── */}
      <footer className="hp-footer">
        <div className="hp-footer-top">
          <div>
            <div className="hp-brand">
              <div className="hp-brand-icon">⚔</div>
              <div className="hp-brand-text">NINE REALMS</div>
            </div>
            <p className="hp-footer-desc">
              Autonomous multi-agent courtroom arbitration system for high-consequence global logistics, maritime trade corridors, and supply chain exposure mitigation.
            </p>
          </div>

          <div className="hp-footer-col">
            <h5>The Realms</h5>
            <ul>
              <li><a href="#realms" onClick={(e) => scrollToSection(e, 'realms')}>Asgard Command</a></li>
              <li><a href="#realms" onClick={(e) => scrollToSection(e, 'realms')}>Midgard Freight</a></li>
              <li><a href="#realms" onClick={(e) => scrollToSection(e, 'realms')}>Alfheim Photonics</a></li>
              <li><a href="#realms" onClick={(e) => scrollToSection(e, 'realms')}>Jotunheim Cold-Chain</a></li>
            </ul>
          </div>

          <div className="hp-footer-col">
            <h5>The Tribunal</h5>
            <ul>
              <li><a href="#tribunal" onClick={(e) => scrollToSection(e, 'tribunal')}>Heimdall Sentinel</a></li>
              <li><a href="#tribunal" onClick={(e) => scrollToSection(e, 'tribunal')}>Thor Defender</a></li>
              <li><a href="#tribunal" onClick={(e) => scrollToSection(e, 'tribunal')}>Loki Arbiter</a></li>
              <li><a href="#tribunal" onClick={(e) => scrollToSection(e, 'tribunal')}>Odin Allfather</a></li>
            </ul>
          </div>

          <div className="hp-footer-col">
            <h5>Trial Systems</h5>
            <ul>
              <li><a href="#workflow" onClick={(e) => scrollToSection(e, 'workflow')}>Workflow Protocol</a></li>
              <li><a href="#arena-preview" onClick={(e) => scrollToSection(e, 'arena-preview')}>Trial Arena</a></li>
              <li><a href="#intelligence" onClick={(e) => scrollToSection(e, 'intelligence')}>Evidence Engine</a></li>
              <li><a href="#hero" onClick={onEnterArena}>Launch Tribunal</a></li>
            </ul>
          </div>
        </div>

        <div className="hp-footer-bottom">
          <div>© {new Date().getFullYear()} NINE REALMS TRIBUNAL · ALL RIGHTS RESERVED.</div>
          <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'center' }}>
            <span>BIFROST TELEMETRY: OPTIMAL</span>
            <span>·</span>
            <span>ENCRYPTION: SHA-256</span>
            <span>·</span>
            <span style={{ color: 'var(--odin-hi)' }}>᚛ ᚠ ᚢ ᚦ ᚬ ᚱ ᚴ ᚜</span>
          </div>
        </div>
      </footer>
    </div>
  )
}
