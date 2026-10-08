// AuthContext.jsx — provides login state to the whole component tree.
//
// WHY React Context?
//   Without context, we would have to pass the session as a prop through
//   every component: App → AnalyzeForm → ... That's called "prop drilling"
//   and it's messy. Context lets any component read the session directly,
//   no matter how deep in the tree it lives.
//
// HOW IT WORKS:
//   1. AuthProvider wraps the whole app in main.jsx.
//   2. It listens to Supabase's onAuthStateChange event, which fires when
//      the user logs in, logs out, or their token refreshes automatically.
//   3. Any component calls useAuth() to get { session, loading }.
//   4. session is null when logged out, or a Supabase session object when
//      logged in. session.access_token is the JWT we send to our backend.

import { createContext, useContext, useEffect, useState } from 'react'
import { supabase } from '../supabaseClient.js'

// createContext() creates the context object.
// The argument (null) is the default value — only used if a component
// renders outside of AuthProvider, which should never happen.
const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  // session: null = logged out, object = logged in
  const [session, setSession] = useState(null)
  // loading: true while we're waiting for Supabase to tell us the initial state
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // getSession() asks Supabase: "is there already a logged-in user?"
    // This handles the case where the user refreshes the page — Supabase
    // stores the session in localStorage and restores it automatically.
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      setLoading(false)
    })

    // onAuthStateChange fires every time auth state changes:
    //   - SIGNED_IN  → user just logged in
    //   - SIGNED_OUT → user just logged out
    //   - TOKEN_REFRESHED → Supabase silently renewed the access token
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setSession(session)
      }
    )

    // Return a cleanup function — React calls this when the component
    // unmounts to stop the Supabase listener and prevent memory leaks.
    return () => subscription.unsubscribe()
  }, [])  // [] = run this effect only once, when the component first mounts

  return (
    // AuthContext.Provider makes session and loading available to all
    // child components that call useAuth().
    <AuthContext.Provider value={{ session, loading }}>
      {children}
    </AuthContext.Provider>
  )
}

// useAuth() is a custom hook — a reusable function that calls useContext.
// Components import this instead of importing AuthContext directly,
// which is cleaner and easier to explain in interviews.
export function useAuth() {
  return useContext(AuthContext)
}
