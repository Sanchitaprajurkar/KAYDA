import React from 'react'
import './RouteMap.css'

/*
  Runemark fictional world: Orvan → Midgard / Tolan grain corridor
  Nodes are placed on a fictional map coordinate system (700×380 viewport)
*/

const NODES = {
  Orvan:    { x: 560, y: 150, label: 'ORVAN [SUSPENDED]', type: 'disrupted' },
  Midgard:  { x: 180, y: 120, label: 'MIDGARD [TERMINUS]', type: 'terminus' },
  Tolan:    { x: 200, y: 250, label: 'TOLAN [TERMINUS]',   type: 'terminus' },
  Vethi:    { x: 390, y: 210, label: 'VETHI [ALT HUB]',    type: 'alt' },
  Asgard:   { x: 420, y: 90,  label: 'ASGARD',             type: 'transit' },
  Dorin:    { x: 310, y: 180, label: 'DORIN',              type: 'transit' },
}

export default function RouteMap() {
  return (
    <div className="route-map">
      {/* Header */}
      <div className="route-map__header">
        <div className="route-map__header-left">
          <span className="route-map__header-dot" />
          <span className="route-map__header-title">RUNEMARK TACTICAL ROUTE MATRIX</span>
        </div>
        <div className="route-map__legend">
          <span className="route-map__legend-item">
            <span className="route-map__legend-line" style={{ background: 'var(--thor)', opacity: 0.8 }} />
            <span style={{ color: 'var(--thor)' }}>Suspended Corridor</span>
          </span>
          <span className="route-map__legend-item">
            <span className="route-map__legend-line" style={{ background: 'var(--text-primary)', opacity: 0.5 }} />
            <span>Primary Route</span>
          </span>
          <span className="route-map__legend-item">
            <span className="route-map__legend-line" style={{ background: 'var(--loki)' }} />
            <span style={{ color: 'var(--loki)' }}>Vethian Alt Route</span>
          </span>
        </div>
      </div>

      {/* SVG Canvas */}
      <div className="route-map__canvas">
        <svg viewBox="0 0 700 380" preserveAspectRatio="xMidYMid meet">
          <defs>
            {/* Disruption glow */}
            <radialGradient id="glowRed" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#E63946" stopOpacity="0.4" />
              <stop offset="100%" stopColor="#E63946" stopOpacity="0" />
            </radialGradient>
            {/* Terminus glow gold */}
            <radialGradient id="glowGold" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#D7B56D" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#D7B56D" stopOpacity="0" />
            </radialGradient>
            {/* Alt route glow */}
            <radialGradient id="glowGreen" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#00C878" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#00C878" stopOpacity="0" />
            </radialGradient>
          </defs>

          {/* Grid lines */}
          <g stroke="#191F1C" strokeWidth="0.5" strokeDasharray="3 4">
            {[95, 190, 285, 380].map(y => (
              <line key={y} x1="0" y1={y} x2="700" y2={y} />
            ))}
            {[140, 280, 420, 560].map(x => (
              <line key={x} x1={x} y1="0" x2={x} y2="380" />
            ))}
          </g>

          {/* ── SUSPENDED primary route: Orvan → Asgard → Dorin → Midgard ── */}
          <path
            d={`M ${NODES.Orvan.x} ${NODES.Orvan.y} L ${NODES.Asgard.x} ${NODES.Asgard.y} L ${NODES.Dorin.x} ${NODES.Dorin.y} L ${NODES.Midgard.x} ${NODES.Midgard.y}`}
            fill="none"
            stroke="#E63946"
            strokeWidth="1.5"
            strokeDasharray="5 4"
            opacity="0.7"
            className="dashes-march"
          />

          {/* ── SUSPENDED primary route: Orvan → Vethi → Tolan ── */}
          <path
            d={`M ${NODES.Orvan.x} ${NODES.Orvan.y} L ${NODES.Vethi.x} ${NODES.Vethi.y} L ${NODES.Tolan.x} ${NODES.Tolan.y}`}
            fill="none"
            stroke="#E63946"
            strokeWidth="1.5"
            strokeDasharray="5 4"
            opacity="0.7"
            className="dashes-march"
          />

          {/* ── ALT route: Vethi → Dorin → Midgard ── */}
          <path
            d={`M ${NODES.Vethi.x} ${NODES.Vethi.y} Q ${NODES.Dorin.x} ${NODES.Dorin.y - 30} ${NODES.Midgard.x} ${NODES.Midgard.y}`}
            fill="none"
            stroke="#00C878"
            strokeWidth="1.3"
          />

          {/* ── ALT route: Vethi → Tolan ── */}
          <path
            d={`M ${NODES.Vethi.x} ${NODES.Vethi.y} L ${NODES.Tolan.x} ${NODES.Tolan.y}`}
            fill="none"
            stroke="#00C878"
            strokeWidth="1.3"
          />

          {/* ═══════════════ NODES ═══════════════ */}

          {/* ORVAN — disrupted */}
          <g transform={`translate(${NODES.Orvan.x}, ${NODES.Orvan.y})`}>
            <circle r="28" fill="url(#glowRed)" />
            <circle className="disruption-ring" r="9" fill="none" stroke="#E63946" strokeWidth="1" opacity="0.5" />
            <circle r="5.5" fill="#E63946" />
            {/* Label box */}
            <rect x="-52" y="-26" width="104" height="16" fill="#111615" stroke="#E63946" strokeWidth="1" />
            <text x="0" y="-15" textAnchor="middle" fill="#E63946" fontSize="8.5" fontFamily="JetBrains Mono, monospace" fontWeight="700">
              ORVAN [SUSPENDED]
            </text>
          </g>

          {/* MIDGARD — terminus (gold) */}
          <g transform={`translate(${NODES.Midgard.x}, ${NODES.Midgard.y})`}>
            <circle r="24" fill="url(#glowGold)" />
            <circle r="5.5" fill="#111615" stroke="#D7B56D" strokeWidth="1.5" />
            <circle r="2.5" fill="#D7B56D" />
            <text x="0" y="18" textAnchor="middle" fill="#D7B56D" fontSize="8.5" fontFamily="JetBrains Mono, monospace" fontWeight="700">
              MIDGARD [TERMINUS]
            </text>
          </g>

          {/* TOLAN — terminus (gold) */}
          <g transform={`translate(${NODES.Tolan.x}, ${NODES.Tolan.y})`}>
            <circle r="24" fill="url(#glowGold)" />
            <circle r="5.5" fill="#111615" stroke="#D7B56D" strokeWidth="1.5" />
            <circle r="2.5" fill="#D7B56D" />
            <text x="0" y="18" textAnchor="middle" fill="#D7B56D" fontSize="8.5" fontFamily="JetBrains Mono, monospace" fontWeight="700">
              TOLAN [TERMINUS]
            </text>
          </g>

          {/* VETHI — alt hub (green) */}
          <g transform={`translate(${NODES.Vethi.x}, ${NODES.Vethi.y})`}>
            <circle r="22" fill="url(#glowGreen)" />
            <circle r="4.5" fill="#00C878" />
            <text x="0" y="-14" textAnchor="middle" fill="#00C878" fontSize="8.5" fontFamily="JetBrains Mono, monospace">
              VETHI [ALT HUB]
            </text>
            <text x="0" y="-5" textAnchor="middle" fill="#00C878" fontSize="7.5" fontFamily="JetBrains Mono, monospace">
              30-35% CAPACITY
            </text>
          </g>

          {/* ASGARD — transit */}
          <g transform={`translate(${NODES.Asgard.x}, ${NODES.Asgard.y})`}>
            <circle r="3" fill="#111615" stroke="#919A95" strokeWidth="1" />
            <text x="6" y="3" fill="#919A95" fontSize="8" fontFamily="JetBrains Mono, monospace">ASGARD</text>
          </g>

          {/* DORIN — transit */}
          <g transform={`translate(${NODES.Dorin.x}, ${NODES.Dorin.y})`}>
            <circle r="3" fill="#111615" stroke="#919A95" strokeWidth="1" />
            <text x="6" y="3" fill="#919A95" fontSize="8" fontFamily="JetBrains Mono, monospace">DORIN</text>
          </g>

          {/* Corridor label */}
          <text x="370" y="140" textAnchor="middle" fill="#E63946" fontSize="9" fontFamily="JetBrains Mono, monospace" opacity="0.6">
            ORVAN CORRIDOR — SUSPENDED 20 JAN 2027
          </text>
        </svg>
      </div>

      {/* Footer telemetry */}
      <div className="route-map__footer">
        <div>
          SUSPENDED VOLUME: <span style={{ color: 'var(--thor)', fontWeight: 600 }}>~1.2M MT/QTR</span>
        </div>
        <div>
          VETHIAN REDIRECT: <span style={{ color: 'var(--loki)', fontWeight: 600 }}>30–35%</span>
        </div>
        <div>
          LEAD TIME: <span style={{ color: 'var(--text-primary)' }}>8–12 DAYS</span>
        </div>
        <div>
          BUFFER COVER: <span style={{ color: 'var(--odin)' }}>TOLAN 68D (WHEAT) / 45D (MAIZE)</span>
        </div>
      </div>
    </div>
  )
}
