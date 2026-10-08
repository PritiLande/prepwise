// api.js — the only file that talks to the backend.
// WHY a separate file? Every component would need to know the URL, the
// error-handling rules, and the fetch logic. Keeping it here means we
// change it in one place and all components benefit automatically.

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

export const MAX_JD_CHARS = 8000
export const MAX_FILE_MB  = 5

// ---------------------------------------------------------------------------
// Helper — build headers with optional Authorization
// ---------------------------------------------------------------------------
// WHY a helper? Both analyzeResume and getHistory need the Bearer token.
// Centralising it here means one place to change if the auth scheme changes.
function _authHeaders(token) {
  // If a token is provided, attach it. Otherwise return an empty object.
  // The spread operator (...) merges it into the fetch options headers.
  return token ? { Authorization: `Bearer ${token}` } : {}
}

// ---------------------------------------------------------------------------
// Helper — parse error responses consistently
// ---------------------------------------------------------------------------
async function _handleErrorResponse(response) {
  let detail = ''
  try {
    const body = await response.json()
    detail = body.detail || ''
  } catch {
    // body was not JSON — fall through to generic messages below
  }

  switch (response.status) {
    case 400:
    case 413:
    case 422:
      throw new Error(detail || 'Invalid input. Please check your file and fields.')
    case 401:
      throw new Error('Please log in to use this feature.')
    case 429:
      throw new Error('Too many requests. Please wait a minute and try again.')
    case 500:
      throw new Error('Something went wrong on our side. Please try again later.')
    case 502:
      throw new Error('The AI gave an unexpected response. Please try again.')
    case 503:
      throw new Error('Service temporarily unavailable. Please try again.')
    case 504:
      throw new Error('The AI took too long to respond. Please try again.')
    default:
      throw new Error(detail || `Unexpected error (${response.status}). Please try again.`)
  }
}

// ---------------------------------------------------------------------------
// analyzeResume — POST /analyze
// ---------------------------------------------------------------------------
/**
 * Send the resume, job description, and company name to POST /analyze.
 * If token is provided, the analysis will be saved to the user's history.
 *
 * @param {File}        resumeFile
 * @param {string}      jobDescription
 * @param {string}      companyName
 * @param {string|null} token  — Supabase JWT, or null for unauthenticated use
 */
export async function analyzeResume(resumeFile, jobDescription, companyName, token = null) {
  const form = new FormData()
  form.append('resume', resumeFile)
  form.append('job_description', jobDescription)
  form.append('company_name', companyName)

  let response
  try {
    response = await fetch(`${API_URL}/analyze`, {
      method: 'POST',
      body: form,
      // Merge the auth header (if any) into the request headers.
      // Do NOT set Content-Type — the browser sets it automatically for FormData.
      headers: _authHeaders(token),
    })
  } catch {
    throw new Error('Cannot reach the server. Check your internet connection and make sure the backend is running.')
  }

  if (!response.ok) await _handleErrorResponse(response)
  return response.json()
}

// ---------------------------------------------------------------------------
// getHistory — GET /analyses
// ---------------------------------------------------------------------------
/**
 * Fetch the authenticated user's past analyses.
 * @param {string} token — Supabase JWT (required)
 */
export async function getHistory(token) {
  let response
  try {
    response = await fetch(`${API_URL}/analyses`, {
      method: 'GET',
      headers: _authHeaders(token),
    })
  } catch {
    throw new Error('Cannot reach the server. Please make sure the backend is running.')
  }
  if (!response.ok) await _handleErrorResponse(response)
  return response.json()
}

// ---------------------------------------------------------------------------
// getAnalysisDetail — GET /analyses/{id}
// ---------------------------------------------------------------------------
/**
 * Fetch the full stored result for one analysis.
 * Returns 404 if the id is unknown or belongs to another user.
 *
 * @param {string} id    — UUID of the analysis record
 * @param {string} token — Supabase JWT (required)
 */
export async function getAnalysisDetail(id, token) {
  let response
  try {
    response = await fetch(`${API_URL}/analyses/${encodeURIComponent(id)}`, {
      method: 'GET',
      // Authorization is required — backend returns 401 without it.
      headers: _authHeaders(token),
    })
  } catch {
    throw new Error('Cannot reach the server. Please make sure the backend is running.')
  }
  if (!response.ok) await _handleErrorResponse(response)
  return response.json()
}
