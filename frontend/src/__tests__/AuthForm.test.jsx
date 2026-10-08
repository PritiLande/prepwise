// Tests for AuthForm.jsx
//
// STRATEGY — mock Supabase entirely.
//   AuthForm calls supabase.auth.signInWithPassword() and supabase.auth.signUp().
//   We replace the entire supabaseClient module with a fake object so no
//   real HTTP requests are made and no real Supabase project is needed.
//
//   vi.mock() intercepts the import at the top of AuthForm.jsx and replaces
//   it with our controlled fake before any test runs.

import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import AuthForm from '../components/AuthForm.jsx'

// ---------------------------------------------------------------------------
// Mock the Supabase client
// ---------------------------------------------------------------------------
// vi.mock() must be at the top level (not inside a test) so Vitest can hoist
// it before imports are resolved. The factory function returns the fake module.
vi.mock('../supabaseClient.js', () => ({
  supabase: {
    auth: {
      signInWithPassword: vi.fn(),
      signUp: vi.fn(),
    },
  },
}))

// Import the mock AFTER vi.mock() so we get the fake version
import { supabase } from '../supabaseClient.js'

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('AuthForm', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders email and password inputs', () => {
    render(<AuthForm />)
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
  })

  it('shows Log In button by default', () => {
    render(<AuthForm />)
    expect(screen.getByRole('button', { name: /log in/i })).toBeInTheDocument()
  })

  it('toggles to Sign Up mode when toggle button is clicked', async () => {
    render(<AuthForm />)
    // Click the "Sign Up" toggle link (may have emoji prefix)
    fireEvent.click(screen.getByRole('button', { name: /sign up/i }))
    // The submit button should now say "Sign Up" (possibly with emoji)
    expect(screen.getByRole('button', { name: /sign up/i })).toBeInTheDocument()
  })

  it('calls signInWithPassword with email and password on login submit', async () => {
    // Make the mock return a success response (no error)
    supabase.auth.signInWithPassword.mockResolvedValue({ error: null })

    render(<AuthForm />)

    await userEvent.type(screen.getByLabelText(/email/i), 'user@example.com')
    await userEvent.type(screen.getByLabelText(/password/i), 'password123')
    fireEvent.click(screen.getByRole('button', { name: /log in/i }))

    await waitFor(() => {
      expect(supabase.auth.signInWithPassword).toHaveBeenCalledWith({
        email: 'user@example.com',
        password: 'password123',
      })
    })
  })

  it('shows error message when login fails', async () => {
    // Simulate Supabase returning an error (wrong password)
    supabase.auth.signInWithPassword.mockResolvedValue({
      error: { message: 'Invalid login credentials' },
    })

    render(<AuthForm />)
    await userEvent.type(screen.getByLabelText(/email/i), 'user@example.com')
    await userEvent.type(screen.getByLabelText(/password/i), 'wrongpassword')
    fireEvent.click(screen.getByRole('button', { name: /log in/i }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
      expect(screen.getByRole('alert').textContent).toMatch(/invalid login/i)
    })
  })

  it('calls signUp and shows success message on successful signup', async () => {
    supabase.auth.signUp.mockResolvedValue({ error: null })

    render(<AuthForm />)
    // Switch to signup mode
    fireEvent.click(screen.getByRole('button', { name: /sign up/i }))

    await userEvent.type(screen.getByLabelText(/email/i), 'new@example.com')
    await userEvent.type(screen.getByLabelText(/password/i), 'newpassword')
    // Submit button says "✨ Sign Up" after toggle — match loosely
    fireEvent.click(screen.getAllByRole('button', { name: /sign up/i })[0])

    await waitFor(() => {
      expect(supabase.auth.signUp).toHaveBeenCalledWith({
        email: 'new@example.com',
        password: 'newpassword',
      })
      // Success message should appear
      expect(screen.getByRole('status')).toBeInTheDocument()
    })
  })
})
