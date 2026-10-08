// HistoryView.jsx — shows the list of past analyses, and when the user
// clicks a card it loads and shows the full analysis detail.
//
// WHY manage both list and detail here (not in App)?
//   The history tab is self-contained: it has its own two states (list
//   view and detail view) that don't affect the rest of the app.
//   Keeping them here means App.jsx stays clean and unaware of this detail.
//
// STATE MACHINE:
//   view === 'list'   → show summary cards
//   view === 'detail' → show full ResultView + back button

import { useEffect, useState } from 'react'
import { getHistory, getAnalysisDetail } from '../api.js'
import ResultView from './ResultView.jsx'

export default function HistoryView({ token }) {
  // ── List state ─────────────────────────────────────────────────
  const [analyses, setAnalyses]     = useState([])
  const [listLoading, setListLoading] = useState(true)
  const [listError, setListError]   = useState('')

  // ── Detail state ───────────────────────────────────────────────
  // view: 'list' | 'detail'
  const [view, setView]               = useState('list')
  const [detail, setDetail]           = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState('')

  // Fetch the list whenever the token changes (e.g. after token refresh)
  useEffect(() => {
    async function fetchHistory() {
      setListLoading(true)
      setListError('')
      try {
        const data = await getHistory(token)
        setAnalyses(data.analyses || [])
      } catch (err) {
        setListError(err.message)
      } finally {
        setListLoading(false)
      }
    }
    fetchHistory()
  }, [token])

  // Called when the user clicks a card
  async function handleCardClick(id) {
    setDetailLoading(true)
    setDetailError('')
    setDetail(null)
    setView('detail')
    try {
      const data = await getAnalysisDetail(id, token)
      setDetail(data)
    } catch (err) {
      setDetailError(err.message)
    } finally {
      setDetailLoading(false)
    }
  }

  function handleBack() {
    setView('list')
    setDetail(null)
    setDetailError('')
  }

  // ── Detail view ─────────────────────────────────────────────────
  if (view === 'detail') {
    return (
      <div>
        <button
          className="back-btn"
          onClick={handleBack}
          aria-label="Back to history list"
        >
          ← Back to History
        </button>

        {detailLoading && (
          <p className="loading-message" role="status">
            Loading analysis…
          </p>
        )}

        {detailError && (
          <div className="error-message" role="alert">
            <strong>Error: </strong>{detailError}
          </div>
        )}

        {/* detail contains company_name, match_score, created_at, result_json.
            ResultView knows how to unwrap result_json if present. */}
        {detail && <ResultView result={detail} />}
      </div>
    )
  }

  // ── List view ───────────────────────────────────────────────────
  if (listLoading) {
    return <p className="loading-message" role="status">Loading your history…</p>
  }

  if (listError) {
    return (
      <div className="error-message" role="alert">
        <strong>Error: </strong>{listError}
      </div>
    )
  }

  if (analyses.length === 0) {
    return (
      <div className="history-empty">
        <p>No saved analyses yet. Run your first analysis to see it here.</p>
      </div>
    )
  }

  return (
    <div className="history-list">
      {analyses.map(item => (
        // button makes the card keyboard-accessible automatically.
        // It responds to Enter and Space, and gets a focus ring.
        <button
          key={item.id}
          className="history-card history-card--clickable"
          onClick={() => handleCardClick(item.id)}
          aria-label={`Open analysis for ${item.company_name}, ${item.match_score} out of 100`}
        >
          <div className="history-card-header">
            <span className="history-company">{item.company_name}</span>
            <span className="history-date">
              {new Date(item.created_at).toLocaleDateString()}
            </span>
          </div>
          <div className="history-score">
            <span className="history-score-label">Match score</span>
            <span className="history-score-value">{item.match_score}/100</span>
          </div>
          <div className="score-bar-track" role="progressbar"
               aria-valuenow={item.match_score} aria-valuemin={0} aria-valuemax={100}
               aria-label={`Match score: ${item.match_score} out of 100`}>
            <div className="score-bar-fill" style={{ width: `${item.match_score}%` }} />
          </div>
          <span className="history-card-cta">Tap to view full analysis →</span>
        </button>
      ))}
    </div>
  )
}
