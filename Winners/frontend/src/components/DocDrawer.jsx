import React, { useState, useEffect } from 'react'
import { FileText, ExternalLink, X, Loader2 } from 'lucide-react'
import { EVIDENCE_REGISTRY } from '../data/trialData'
import { getCorpusDocument } from '../services/api'
import './DocDrawer.css'

const STATUS_STYLE = {
  VERIFIED:  { color: 'var(--loki)',  border: 'var(--loki-border)',  bg: 'var(--loki-dim)'  },
  CONTESTED: { color: 'var(--thor)',  border: 'var(--thor-border)',  bg: 'var(--thor-dim)'  },
  FLAGGED:   { color: 'var(--thor)',  border: 'var(--thor-border)',  bg: 'var(--thor-dim)'  },
}

function ReliabilityBar({ tier }) {
  return (
    <div className="doc-reliability-bar">
      {[1, 2, 3, 4].map(i => (
        <div
          key={i}
          className="doc-reliability-pip"
          style={{
            background: i <= tier
              ? tier === 1 ? 'var(--loki)'
              : tier === 2 ? 'var(--odin)'
              : tier === 3 ? 'var(--thor)'
              : '#555'
              : 'var(--border)',
          }}
        />
      ))}
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-secondary)', marginLeft: 4 }}>
        TIER {tier}
      </span>
    </div>
  )
}

export default function DocDrawer({ docId, onClose }) {
  const [liveDoc, setLiveDoc] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!docId) {
      setLiveDoc(null)
      return
    }
    
    // Check if in local registry
    if (EVIDENCE_REGISTRY[docId]) {
      setLiveDoc(EVIDENCE_REGISTRY[docId])
      return
    }

    // Otherwise fetch from backend API
    setLoading(true)
    getCorpusDocument(docId)
      .then(data => {
        setLiveDoc({
          id: data.doc_id,
          title: data.title,
          source: data.source_name,
          sourceType: data.source_type,
          timestamp: `${data.pub_date} ${data.pub_time} UTC`,
          pubDate: data.pub_date,
          snippet: data.paragraphs?.[0] || data.content.slice(0, 300),
          status: data.is_retracted ? 'FLAGGED' : 'VERIFIED',
          reliability: data.reliability,
          sector: data.sector,
          country: data.country,
          content: data.content,
          claims: []
        })
      })
      .catch(() => {
        setLiveDoc(null)
      })
      .finally(() => setLoading(false))
  }, [docId])

  if (!docId) return null

  const doc = liveDoc || EVIDENCE_REGISTRY[docId]
  const ss = doc ? (STATUS_STYLE[doc.status] || STATUS_STYLE.VERIFIED) : null

  return (
    <div className="doc-drawer-overlay">
      <div className="doc-drawer">
        {/* Header */}
        <div className="doc-drawer__header">
          <div className="doc-drawer__header-left">
            <FileText size={13} />
            EXHIBIT AUDIT // [{docId}]
          </div>
          <button className="doc-drawer__close" onClick={onClose}>
            <X size={12} />
          </button>
        </div>

        {doc ? (
          <>
            <div className="doc-drawer__body">
              {/* Title */}
              <div className="doc-field">
                <span className="doc-field__label">DOCUMENT TITLE</span>
                <span className="doc-field__val">{doc.title}</span>
              </div>

              {/* Meta grid */}
              <div className="doc-meta-grid">
                <div className="doc-field">
                  <span className="doc-field__label">SOURCE</span>
                  <span className="doc-field__val" style={{ fontSize: 10.5 }}>{doc.source}</span>
                </div>
                <div className="doc-field">
                  <span className="doc-field__label">TIMESTAMP</span>
                  <span className="doc-field__val" style={{ fontSize: 10.5 }}>{doc.timestamp}</span>
                </div>
                <div className="doc-field">
                  <span className="doc-field__label">SECTOR</span>
                  <span className="doc-field__val" style={{ fontSize: 10.5, textTransform: 'uppercase' }}>
                    {doc.sector}
                  </span>
                </div>
                <div className="doc-field">
                  <span className="doc-field__label">COUNTRY</span>
                  <span className="doc-field__val" style={{ fontSize: 10.5 }}>{doc.country}</span>
                </div>
              </div>

              {/* Status + Reliability */}
              <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                <div className="doc-field">
                  <span className="doc-field__label">VERIFICATION</span>
                  <span
                    className="doc-status-badge"
                    style={{ color: ss.color, borderColor: ss.border, background: ss.bg }}
                  >
                    {doc.status}
                  </span>
                </div>
                <div className="doc-field">
                  <span className="doc-field__label">RELIABILITY</span>
                  <ReliabilityBar tier={parseInt(doc.reliability)} />
                </div>
              </div>

              {/* Snippet */}
              <div className="doc-field">
                <span className="doc-field__label">INTELLIGENCE EXTRACT</span>
                <div className="doc-snippet">
                  &ldquo;{doc.snippet}&rdquo;
                </div>
              </div>

              {/* Claims that cite this */}
              {doc.claims?.length > 0 && (
                <div className="doc-field">
                  <span className="doc-field__label">CITED BY CLAIMS</span>
                  <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                    {doc.claims.map(c => (
                      <span key={c} style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: 9.5,
                        padding: '2px 6px',
                        border: '1px solid var(--border-hi)',
                        color: c.startsWith('TH') ? 'var(--thor)' : 'var(--loki)',
                        background: c.startsWith('TH') ? 'var(--thor-dim)' : 'var(--loki-dim)',
                      }}>
                        {c}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="doc-drawer__footer">
              <span className="doc-drawer__hash">SHA-256: e8f3…{docId.toLowerCase().replace('-','').slice(0,4)}a9b2</span>
              <button className="doc-drawer__ext-link">
                <ExternalLink size={10} />
                ORIGINAL SOURCE
              </button>
            </div>
          </>
        ) : (
          <div className="doc-missing">
            DOCUMENT [{docId}] NOT INDEXED<br />IN LOCAL EVIDENCE VAULT
          </div>
        )}
      </div>
    </div>
  )
}
