import React, { useState } from 'react'
import {
  Scale,
  BookOpen,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  AlertTriangle
} from 'lucide-react'
import './OdinBench.css'

export default function OdinBench({ findings, meta, onDocClick }) {
  const [selectedFindingId, setSelectedFindingId] = useState(null)

  // Structured findings supported by the trial
  const verdictRows = [
    {
      id: 'country-exposure',
      finding: 'Country exposure',
      assessment: 'Established',
      assessmentType: 'established',
      explanation: "Midgard's 54% wheat and 38% maize dependence on the Orvan corridor is established from verified government trade data. Tolan's 68-day buffer reserves prevent acute quarterly food-security breach.",
      primaryDoc: 'ORV-0023',
      secondaryDoc: 'ORV-0031',
      sourceLabel: 'ORV-0023, ORV-0031'
    },
    {
      id: 'sector-disruption',
      finding: 'Sector disruption',
      assessment: 'Established',
      assessmentType: 'established',
      explanation: 'Bulk agricultural trade corridor suspended under force majeure. Spot futures surged +12%, and alternate forward contracts reflect +18% physical delivery premiums.',
      primaryDoc: 'ORV-0017',
      secondaryDoc: 'ORV-0038',
      sourceLabel: 'ORV-0017, ORV-0038'
    },
    {
      id: 'alternative-routes',
      finding: 'Alternative supply routes',
      assessment: 'Contested',
      assessmentType: 'contested',
      explanation: 'Vethian overland rail corridor can absorb 30–35% of displaced volume, but customs fast-tracking is not yet confirmed by sovereign treaty.',
      primaryDoc: 'ORV-0044',
      secondaryDoc: null,
      sourceLabel: 'ORV-0044'
    }
  ]

  const overallAssessment = meta?.exposureFinal?.max === '$210M' || meta?.confidence >= 80
    ? 'Significant exposure'
    : 'Limited exposure'

  return (
    <section className="odin-tribunal">
      {/* ── Tribunal Verdict Header ── */}
      <div className="odin-tribunal__header">
        <div className="odin-tribunal__title-group">
          <div className="odin-tribunal__emblem">
            <Scale size={16} />
          </div>
          <div className="odin-tribunal__headline">
            <h2 className="odin-tribunal__title">⚖️ Odin&apos;s Verdict</h2>
            <div className="odin-tribunal__assessment-row">
              <span className="odin-tribunal__assessment-label">Overall assessment:</span>
              <span className="odin-tribunal__assessment-badge badge-significant">
                {overallAssessment}
              </span>
              <span className="odin-tribunal__exposure-range">
                Net Exposure: {meta?.exposureFinal?.min || '$87M'} — {meta?.exposureFinal?.max || '$210M'} USD ({meta?.confidence || 94}% Certainty)
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* ── Structured Verdict Table ── */}
      <div className="odin-tribunal__table-wrap">
        <table className="odin-tribunal__table">
          <thead>
            <tr>
              <th className="th-finding">Finding</th>
              <th className="th-assessment">Assessment</th>
              <th className="th-explanation">Judicial Summary</th>
              <th className="th-evidence">Evidence</th>
            </tr>
          </thead>
          <tbody>
            {verdictRows.map((row) => {
              const isSelected = selectedFindingId === row.id
              return (
                <React.Fragment key={row.id}>
                  <tr 
                    className={`odin-row ${isSelected ? 'row-selected' : ''}`}
                    onClick={() => setSelectedFindingId(isSelected ? null : row.id)}
                  >
                    <td className="td-finding">
                      <div className="finding-title-row">
                        <strong>{row.finding}</strong>
                        {isSelected ? <ChevronUp size={12} className="chevron-toggle" /> : <ChevronDown size={12} className="chevron-toggle" />}
                      </div>
                    </td>
                    <td className="td-assessment">
                      <span className={`assessment-badge badge-${row.assessmentType}`}>
                        {row.assessment === 'Established' && <CheckCircle2 size={11} />}
                        {row.assessment === 'Contested' && <AlertTriangle size={11} />}
                        <span>{row.assessment}</span>
                      </span>
                    </td>
                    <td className="td-explanation">
                      <p className="finding-summary-text">{row.explanation}</p>
                    </td>
                    <td className="td-evidence" onClick={(e) => e.stopPropagation()}>
                      <button
                        className="odin-view-source-btn"
                        onClick={() => onDocClick(row.primaryDoc)}
                        title={`View supporting evidence in ${row.sourceLabel}`}
                      >
                        <BookOpen size={12} />
                        <span>View source</span>
                        <ExternalLink size={10} className="ext-icon" />
                      </button>
                    </td>
                  </tr>

                  {/* Expanded detail on row click */}
                  {isSelected && (
                    <tr className="odin-expanded-row">
                      <td colSpan={4}>
                        <div className="expanded-explanation-box animate-fade-in">
                          <div className="expanded-box-header">
                            <span className="expanded-box-title">Supporting Judicial Evidence & Exhibits</span>
                            <span className="expanded-box-id">{row.sourceLabel}</span>
                          </div>
                          <p className="expanded-box-desc">{row.explanation}</p>
                          <div className="expanded-box-actions">
                            <button
                              className="expanded-inspect-btn"
                              onClick={() => onDocClick(row.primaryDoc)}
                            >
                              <BookOpen size={12} />
                              <span>Inspect Exhibit {row.primaryDoc}</span>
                            </button>
                            {row.secondaryDoc && (
                              <button
                                className="expanded-inspect-btn"
                                onClick={() => onDocClick(row.secondaryDoc)}
                              >
                                <BookOpen size={12} />
                                <span>Inspect Exhibit {row.secondaryDoc}</span>
                              </button>
                            )}
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}
