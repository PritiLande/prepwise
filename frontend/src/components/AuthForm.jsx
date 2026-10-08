// AuthForm.jsx — login and signup form in one component.
//
// WHY one component for both?
//   Login and signup share the same two fields (email + password).
//   A single component with a toggle keeps the code DRY (Don't Repeat Yourself).
//
// WHAT THIS DOES:
//   - Shows email and password inputs.
//   - Toggles between "Log In" and "Sign Up" modes.
//   - Calls Supabase Auth directly from the browser — no backend route needed.
//   - On success, AuthContext picks up the new session via onAuthStateChange.

import { useState } from 'react'
import { supabase } from '../supabaseClient.js'

export default function AuthForm() {
  // mode controls which Supabase method we call on submit
  const [mode, setMode]       = useState('login')   // 'login' | 'signup'
  const [email, setEmail]     = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]     = useState('')
  const [message, setMessage] = useState('')  // success message for signup
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()  // stop the browser reloading the page
    setError('')
    setMessage('')
    setLoading(true)

    if (mode === 'signup') {
      // signUp creates a new Supabase Auth user.
      // Supabase will send a confirmation email unless you disable it
      // in your dashboard (Authentication → Settings → Confirm email).
      const { error } = await supabase.auth.signUp({ email, password })
      if (error) {
        setError(error.message)
      } else {
        setMessage('Account created! Check your email to confirm, then log in.')
      }
    } else {
      // signInWithPassword checks email + password and returns a session.
      // On success, onAuthStateChange in AuthContext fires automatically.
      const { error } = await supabase.auth.signInWithPassword({ email, password })
      if (error) setError(error.message)
      // No need to do anything on success — AuthContext handles it.
    }

    setLoading(false)
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h2 className="auth-title">
          {mode === 'login' ? '🔐 Log In' : '✨ Create Account'}
        </h2>

        {error   && <div className="error-message"  role="alert"><strong>Error: </strong>{error}</div>}
        {message && <div className="success-message" role="status">{message}</div>}

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="form-group">
            <label htmlFor="auth-email">📧 Email</label>
            <input
              id="auth-email"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              disabled={loading}
              autoComplete="email"
            />
          </div>

          <div className="form-group">
            <label htmlFor="auth-password">🔒 Password</label>
            <input
              id="auth-password"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="Minimum 6 characters"
              required
              disabled={loading}
              minLength={6}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            />
          </div>

          <button
            type="submit"
            className="submit-btn"
            disabled={loading}
            aria-busy={loading}
          >
            {loading
              ? '⏳ Please wait…'
              : mode === 'login' ? '🔐 Log In' : '✨ Sign Up'}
          </button>
        </form>

        {/* Toggle between login and signup */}
        <p className="auth-toggle">
          {mode === 'login'
            ? "Don't have an account? "
            : 'Already have an account? '}
          <button
            className="link-btn"
            onClick={() => { setMode(mode === 'login' ? 'signup' : 'login'); setError(''); setMessage('') }}
          >
            {mode === 'login' ? 'Sign Up' : 'Log In'}
          </button>
        </p>
      </div>
    </div>
  )
}
