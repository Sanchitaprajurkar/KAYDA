import React, { useState } from 'react'
import { Sparkles, Layers } from 'lucide-react'
import './RouteMap.css'

/*
  Nine Realms / Runemark Fictional World Coordinate System:
  Viewport 760 x 440
*/
const REALM_NODES = {
  Orvan: {
    id: 'Orvan',
    name: 'Orvan',
    realmTitle: 'The Grain Nexus · Disrupted Origin',
    status: 'Corridor Suspended',
    statusType: 'disrupted',
    x: 610,
    y: 170,
    lore: 'Transit committee halted the grain corridor under force-majeure following unresolved customs disputes. Over 1.2M metric tons of quarterly supply remain stranded.',
    keyMetric: 'Deficit: ~1.2M MT stranded',
    condition: 'Force-Majeure Declaration active'
  },
  Midgard: {
    id: 'Midgard',
    name: 'Midgard',
    realmTitle: 'Mortal Realm · Import Dependent',
    status: 'Severe Vulnerability',
    statusType: 'terminus',
    x: 150,
    y: 130,
    lore: 'Historically relies on Orvan for 54% of wheat and 38% of maize imports. Possesses zero active backup contracts for Q1, exposing its markets to violent price spikes.',
    keyMetric: 'Dependency: 54% Wheat / 38% Maize',
    condition: 'Immediate spot inflation exposure'
  },
  Tolan: {
    id: 'Tolan',
    name: 'Tolan',
    realmTitle: 'Strategic Granary · Buffer Terminus',
    status: 'Buffer Insulated',
    statusType: 'terminus',
    x: 180,
    y: 290,
    lore: 'Maintains 68 days of wheat and 45 days of maize in state reserves, sheltering its population from acute quarterly food supply disruption.',
    keyMetric: 'Reserves: 68-day wheat buffer',
    condition: 'Sheltered from immediate breach'
  },
  Vethi: {
    id: 'Vethi',
    name: 'Vethi',
    realmTitle: 'Overland Bastion · Mitigation Hub',
    status: 'Active Diversion',
    statusType: 'alt',
    x: 400,
    y: 260,
    lore: 'Overland corridors offer emergency capacity to redirect 30–35% of stranded grain to Midgard and Tolan with an estimated 8–12 day transit lead time.',
    keyMetric: 'Capacity: 30–35% absorption',
    condition: '8–12 days transit lead time'
  },
  Asgard: {
    id: 'Asgard',
    name: 'Asgard',
    realmTitle: 'The High Realm · Judicial Oversight',
    status: 'Sovereign Nexus',
    statusType: 'transit',
    x: 460,
    y: 85,
    lore: 'Seat of the Allfather and High Tribunal. Oversees the enforcement of inter-realm trade covenants and authenticates verified intelligence.',
    keyMetric: 'Authority: Treaty arbitration',
    condition: 'Neutral judicial sanctuary'
  },
  Dorin: {
    id: 'Dorin',
    name: 'Dorin',
    realmTitle: 'Iron Crossroads · Canal Junction',
    status: 'Active Crossing',
    statusType: 'transit',
    x: 300,
    y: 190,
    lore: 'Central canal switching junction connecting northern and southern trade routes. Crucial nexus for Vethian overland grain diversion.',
    keyMetric: 'Capacity: 40k MT/week rail/canal',
    condition: 'Optimal operational transit'
  }
}

export default function RouteMap() {
  const [hoveredNode, setHoveredNode] = useState(null)
  const [selectedNode, setSelectedNode] = useState('Orvan')
  const [filterMode, setFilterMode] = useState('ALL') // ALL, SUSPENDED, ALT

  const activeData = hoveredNode ? REALM_NODES[hoveredNode] : REALM_NODES[selectedNode]

  return (
    <div className="realm-matrix">
      {/* ── Realm Matrix Header ── */}
      <div className="realm-matrix__header">
        <div className="realm-matrix__title-group">
          <h3 className="realm-matrix__title">Yggdrasil Trade Corridors</h3>
          <span className="realm-matrix__subtitle">The Living Tapestry of Realm Supply & Disruption</span>
        </div>

        {/* View Mode Filters */}
        <div className="realm-matrix__views">
          <button 
            className={`realm-matrix__view-btn ${filterMode === 'ALL' ? 'active' : ''}`}
            onClick={() => setFilterMode('ALL')}
          >
            All Corridors
          </button>
          <button 
            className={`realm-matrix__view-btn ${filterMode === 'SUSPENDED' ? 'active' : ''}`}
            onClick={() => setFilterMode('SUSPENDED')}
          >
            <span className="pip pip--crimson" /> Suspended
          </button>
          <button 
            className={`realm-matrix__view-btn ${filterMode === 'ALT' ? 'active' : ''}`}
            onClick={() => setFilterMode('ALT')}
          >
            <span className="pip pip--emerald" /> Mitigated
          </button>
        </div>
      </div>

      {/* ── Celestial Map Canvas ── */}
      <div className="realm-matrix__canvas-wrap">
        <svg 
          viewBox="0 0 760 440" 
          className="realm-matrix__svg"
          preserveAspectRatio="xMidYMid meet"
        >
          <defs>
            {/* Ambient Background Nebula */}
            <radialGradient id="celestialVoid" cx="50%" cy="50%" r="55%">
              <stop offset="0%" stopColor="#1B221E" stopOpacity="0.7" />
              <stop offset="60%" stopColor="#151916" stopOpacity="0.4" />
              <stop offset="100%" stopColor="#0D0F0E" stopOpacity="0" />
            </radialGradient>

            {/* Realm Node Auras */}
            <radialGradient id="auraCrimson" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#D94848" stopOpacity="0.4" />
              <stop offset="100%" stopColor="#D94848" stopOpacity="0" />
            </radialGradient>

            <radialGradient id="auraEmerald" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#19B77A" stopOpacity="0.4" />
              <stop offset="100%" stopColor="#19B77A" stopOpacity="0" />
            </radialGradient>

            <radialGradient id="auraGold" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#D7AD62" stopOpacity="0.4" />
              <stop offset="100%" stopColor="#D7AD62" stopOpacity="0" />
            </radialGradient>

            <filter id="celestialGlow" x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/* Celestial Void Glow */}
          <rect width="760" height="440" fill="url(#celestialVoid)" />

          {/* Mythic Ley Lines / Concentric Ring Guides */}
          <circle cx="380" cy="220" r="190" fill="none" stroke="rgba(215, 173, 98, 0.04)" strokeWidth="1" strokeDasharray="4 8" />
          <circle cx="380" cy="220" r="110" fill="none" stroke="rgba(215, 173, 98, 0.04)" strokeWidth="1" />
          
          {/* Subtle Celestial Star Pips */}
          {[[90, 80], [670, 70], [680, 370], [100, 380], [380, 40], [520, 360], [240, 60]].map(([sx, sy], i) => (
            <circle key={`star-${i}`} cx={sx} cy={sy} r="1" fill="#F4F0E7" opacity="0.25" />
          ))}

          {/* ═══════════ TRADE LEY LINES ═══════════ */}

          {/* ── 1. Suspended Corridor (Orvan -> Asgard -> Dorin -> Midgard) ── */}
          {(filterMode === 'ALL' || filterMode === 'SUSPENDED') && (
            <g className="corridor-flow">
              <path
                d={`M ${REALM_NODES.Orvan.x} ${REALM_NODES.Orvan.y} 
                    Q 540 95 ${REALM_NODES.Asgard.x} ${REALM_NODES.Asgard.y} 
                    T ${REALM_NODES.Dorin.x} ${REALM_NODES.Dorin.y} 
                    Q 220 145 ${REALM_NODES.Midgard.x} ${REALM_NODES.Midgard.y}`}
                fill="none"
                stroke="#D94848"
                strokeWidth="2"
                strokeDasharray="6 6"
                className="ley-line--suspended"
                filter="url(#celestialGlow)"
              />
            </g>
          )}

          {/* ── 2. Suspended Southern Branch (Orvan -> Vethi -> Tolan) ── */}
          {(filterMode === 'ALL' || filterMode === 'SUSPENDED') && (
            <g className="corridor-flow">
              <path
                d={`M ${REALM_NODES.Orvan.x} ${REALM_NODES.Orvan.y} 
                    Q 510 240 ${REALM_NODES.Vethi.x} ${REALM_NODES.Vethi.y} 
                    L ${REALM_NODES.Tolan.x} ${REALM_NODES.Tolan.y}`}
                fill="none"
                stroke="#D94848"
                strokeWidth="1.6"
                strokeDasharray="5 5"
                opacity="0.75"
                className="ley-line--suspended"
              />
            </g>
          )}

          {/* ── 3. Mitigated Alternative Route (Vethi -> Dorin -> Midgard) ── */}
          {(filterMode === 'ALL' || filterMode === 'ALT') && (
            <g className="corridor-flow">
              <path
                d={`M ${REALM_NODES.Vethi.x} ${REALM_NODES.Vethi.y} 
                    Q ${REALM_NODES.Dorin.x} ${REALM_NODES.Dorin.y + 40} ${REALM_NODES.Midgard.x} ${REALM_NODES.Midgard.y}`}
                fill="none"
                stroke="#19B77A"
                strokeWidth="2.2"
                strokeDasharray="8 6"
                className="ley-line--mitigated"
                filter="url(#celestialGlow)"
              />
            </g>
          )}

          {/* ── 4. Mitigated Branch (Vethi -> Tolan) ── */}
          {(filterMode === 'ALL' || filterMode === 'ALT') && (
            <g className="corridor-flow">
              <path
                d={`M ${REALM_NODES.Vethi.x} ${REALM_NODES.Vethi.y} 
                    Q 285 305 ${REALM_NODES.Tolan.x} ${REALM_NODES.Tolan.y}`}
                fill="none"
                stroke="#19B77A"
                strokeWidth="1.8"
                strokeDasharray="7 5"
                opacity="0.85"
                className="ley-line--mitigated"
              />
            </g>
          )}

          {/* ═══════════ REALM CELESTIAL NODES ═══════════ */}
          {Object.values(REALM_NODES).map((node) => {
            const isSelected = selectedNode === node.id
            const isHovered = hoveredNode === node.id
            const isDisrupted = node.statusType === 'disrupted'
            const isTerminus = node.statusType === 'terminus'
            const isAlt = node.statusType === 'alt'

            let nodeColor = '#A5AAA5'
            let auraGrad = null

            if (isDisrupted) {
              nodeColor = '#D94848'
              auraGrad = 'url(#auraCrimson)'
            } else if (isTerminus) {
              nodeColor = '#D7AD62'
              auraGrad = 'url(#auraGold)'
            } else if (isAlt) {
              nodeColor = '#19B77A'
              auraGrad = 'url(#auraEmerald)'
            }

            return (
              <g
                key={node.id}
                transform={`translate(${node.x}, ${node.y})`}
                className={`celestial-realm ${isSelected ? 'celestial-realm--selected' : ''}`}
                onMouseEnter={() => setHoveredNode(node.id)}
                onMouseLeave={() => setHoveredNode(null)}
                onClick={() => setSelectedNode(node.id)}
              >
                {/* Atmospheric Glow Aura */}
                {auraGrad && (
                  <circle 
                    r={isSelected || isHovered ? 36 : 26} 
                    fill={auraGrad} 
                  />
                )}

                {/* Selection Halo Ring */}
                {isSelected && (
                  <circle
                    r="16"
                    fill="none"
                    stroke="#D7AD62"
                    strokeWidth="1.2"
                    strokeDasharray="4 3"
                    className="celestial-halo"
                  />
                )}

                {/* Star Core */}
                <circle
                  r={isDisrupted || isTerminus ? 7 : 5.5}
                  fill="#151916"
                  stroke={nodeColor}
                  strokeWidth="2"
                  filter={isSelected || isHovered ? 'url(#celestialGlow)' : undefined}
                />
                <circle
                  r={isDisrupted || isTerminus ? 3.5 : 2.5}
                  fill={nodeColor}
                />

                {/* Ethereal Realm Nameplate */}
                <text
                  x="0"
                  y="24"
                  textAnchor="middle"
                  fill={isSelected ? '#F4F0E7' : nodeColor}
                  fontSize="12"
                  fontFamily="var(--font-display)"
                  fontWeight="700"
                  letterSpacing="0.06em"
                  className="realm-title-text"
                >
                  {node.name}
                </text>
              </g>
            )
          })}
        </svg>

        {/* ── Strategic Chronicle Floating Lore Card ── */}
        {activeData && (
          <div className="realm-chronicle">
            <div className="realm-chronicle__header">
              <div className="realm-chronicle__titles">
                <span className="realm-chronicle__name">{activeData.name}</span>
                <span className="realm-chronicle__role">{activeData.realmTitle}</span>
              </div>
              <span className={`realm-chronicle__status-pip type--${activeData.statusType}`}>
                {activeData.status}
              </span>
            </div>

            <p className="realm-chronicle__lore">{activeData.lore}</p>

            <div className="realm-chronicle__stats">
              <span className="realm-chronicle__stat-item">
                <strong>Strategic Impact:</strong> {activeData.keyMetric}
              </span>
              <span className="realm-chronicle__stat-item">
                <strong>Status:</strong> {activeData.condition}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* ── Realm Chronicle Bottom Strip ── */}
      <div className="realm-matrix__footer">
        <div className="realm-matrix__foot-stat">
          <span className="pip pip--crimson" />
          <span className="realm-matrix__foot-label">Disrupted Supply:</span>
          <span className="realm-matrix__foot-val color--crimson">~1.2M MT / Quarter</span>
        </div>

        <div className="realm-matrix__foot-stat">
          <span className="pip pip--emerald" />
          <span className="realm-matrix__foot-label">Overland Diversion:</span>
          <span className="realm-matrix__foot-val color--emerald">30–35% Absorption (Vethi)</span>
        </div>

        <div className="realm-matrix__foot-stat">
          <span className="pip pip--gold" />
          <span className="realm-matrix__foot-label">Strategic Reserves:</span>
          <span className="realm-matrix__foot-val color--gold">Tolan 68d Wheat / 45d Maize</span>
        </div>
      </div>
    </div>
  )
}
