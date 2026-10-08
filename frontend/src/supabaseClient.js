// supabaseClient.js — creates ONE Supabase JS client for the whole app.
//
// WHY a single shared instance?
//   The Supabase client maintains an internal session (the logged-in user's
//   token). If we created a new client in every component, each one would
//   have its own disconnected session. One shared instance = one source of truth.
//
// WHY import.meta.env?
//   Vite replaces import.meta.env.VITE_* at build time with the actual values
//   from .env. Variables without the VITE_ prefix are never exposed to the browser.

import { createClient } from '@supabase/supabase-js'

const supabaseUrl  = import.meta.env.VITE_SUPABASE_URL
const supabaseKey  = import.meta.env.VITE_SUPABASE_ANON_KEY

// createClient(url, anonKey) returns a client object with methods like
// .auth.signUp(), .auth.signInWithPassword(), .auth.signOut(), etc.
export const supabase = createClient(supabaseUrl, supabaseKey)
