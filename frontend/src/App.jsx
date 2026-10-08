// App.jsx — root component.
//
// WHAT CHANGED IN PHASE 7:
//   - useAuth() gives us the current session (null = logged out).
//   - A top nav shows the user's email + Logout when logged in.
//   - Two tabs: "Analyse" (the original form) and "History" (past analyses).
//   - The JWT token is passed to analyzeResume() so saves happen automatically.
//   - When logged out, the form still works — analyses just aren't saved.

import { useState } from 'react'
import { useAuth } from './context/AuthContext.jsx'
import { supabase } from './supabaseClient.js'
import { analyzeResume } from './api.js'
import AnalyzeForm from './components/AnalyzeForm.jsx'
import ResultView from './components/ResultView.jsx'
import ErrorMessage from './components/ErrorMessage.jsx'
import AuthForm from './components/AuthForm.jsx'
import HistoryView from './components/HistoryView.jsx'

export default function App() {
  // ── Auth state (from context) ──────────────────────────────────
  // session is the full Supabase session object; null when logged out.
  // session.access_token is the JWT we send to our backend.
  const { session, loading: authLoading } = useAuth()

  // ── App state ──────────────────────────────────────────────────
  const [result, setResult]   = useState(null)
  const [error, setError]     = useState(null)
  const [loading, setLoading] = useState(false)

  // 'analyze' | 'history' | 'auth'
  const [tab, setTab] = useState('analyze')

  // ── Handlers ───────────────────────────────────────────────────
  async function handleSubmit(resumeFile, jobDescription, companyName) {
    setLoading(true)
    setError(null)
    setResult(null)

    // Pass the JWT token if the user is logged in.
    // If null, the backend still works but won't save the analysis.
    const token = session?.access_token ?? null

    try {
      const data = await analyzeResume(resumeFile, jobDescription, companyName, token)
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleLogout() {
    await supabase.auth.signOut()
    // AuthContext's onAuthStateChange listener sets session to null automatically.
    setResult(null)
    setError(null)
    setTab('analyze')
  }

  // ── While Supabase is restoring the session from storage ───────
  if (authLoading) {
    return (
      <div className="app-container">
        <p className="loading-message" role="status">Loading…</p>
      </div>
    )
  }

  return (
    <div className="app-container">

      {/* ── Header ──────────────────────────────────────────────── */}
      <header className="app-header">
        <h1>🎯 Prepwise</h1>
        <p className="app-subtitle">
          Upload your resume, paste a job description, and get a match score,
          skill gaps, and tailored interview questions.
        </p>

        {/* Show user email + logout when logged in */}
        {session && (
          <div className="user-bar">
            <span className="user-email">{session.user.email}</span>
            <button className="logout-btn" onClick={handleLogout}>
              Log Out
            </button>
          </div>
        )}
      </header>

      {/* ── Navigation tabs ─────────────────────────────────────── */}
      <nav className="tab-nav" aria-label="Main navigation">
        <button
          className={'tab-btn' + (tab === 'analyze' ? ' tab-btn--active' : '')}
          onClick={() => setTab('analyze')}
          aria-current={tab === 'analyze' ? 'page' : undefined}
        >
          📄 Analyse
        </button>

        {/* Only show History tab when logged in */}
        {session && (
          <button
            className={'tab-btn' + (tab === 'history' ? ' tab-btn--active' : '')}
            onClick={() => setTab('history')}
            aria-current={tab === 'history' ? 'page' : undefined}
          >
            🕒 History
          </button>
        )}

        {/* Show Auth tab only when logged out */}
        {!session && (
          <button
            className={'tab-btn' + (tab === 'auth' ? ' tab-btn--active' : '')}
            onClick={() => setTab('auth')}
            aria-current={tab === 'auth' ? 'page' : undefined}
          >
            🔐 Log In / Sign Up
          </button>
        )}
      </nav>

      {/* ── Main content (one tab visible at a time) ────────────── */}
      <main>
        {tab === 'analyze' && (
          <>
            {/* Soft nudge to log in — not a hard block */}
            {!session && (
              <p className="auth-nudge">
                <button className="link-btn" onClick={() => setTab('auth')}>
                  Log in
                </button>
                {' '}to save your analyses and view your history.
              </p>
            )}

            <AnalyzeForm onSubmit={handleSubmit} isLoading={loading} />

            {loading && (
              <p className="loading-message" role="status" aria-live="polite">
                ⏳ Analysing your resume… this can take up to a minute.
              </p>
            )}

            <ErrorMessage message={error} />
            <ResultView result={result} />
          </>
        )}

        {tab === 'history' && session && (
          // Pass the JWT token down to HistoryView so it can call GET /analyses
          <HistoryView token={session.access_token} />
        )}

        {tab === 'auth' && !session && (
          <AuthForm />
        )}
      </main>

      <footer className="app-footer">
        <p>🎯 Prepwise · AI-powered interview prep</p>
      </footer>
    </div>
  )
}
