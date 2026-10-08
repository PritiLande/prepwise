// AnalyzeForm — the input form.
// WHY separate from App? App owns the state (result, loading, error).
// This component only owns what the user is typing RIGHT NOW.
// That separation keeps each file focused on one job.

import { useState } from 'react'
import { MAX_JD_CHARS, MAX_FILE_MB } from '../api.js'

export default function AnalyzeForm({ onSubmit, isLoading }) {
  // useState returns [currentValue, setterFunction].
  // Every time a setter is called, React re-renders the component.
  const [resumeFile, setResumeFile]         = useState(null)
  const [jobDescription, setJobDescription] = useState('')
  const [companyName, setCompanyName]       = useState('')
  // clientError shows validation mistakes before we even call the server.
  const [clientError, setClientError]       = useState('')

  function handleFileChange(e) {
    const file = e.target.files[0]
    if (!file) return

    // Client-side guard: only PDFs.
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setClientError('Please select a PDF file.')
      setResumeFile(null)
      e.target.value = ''   // reset the file input
      return
    }
    // Client-side guard: max size.
    if (file.size > MAX_FILE_MB * 1024 * 1024) {
      setClientError(`File must be smaller than ${MAX_FILE_MB} MB.`)
      setResumeFile(null)
      e.target.value = ''
      return
    }
    setClientError('')
    setResumeFile(file)
  }

  function handleSubmit(e) {
    // Prevent the default HTML form behaviour (page reload).
    e.preventDefault()

    // Final client-side validation before hitting the server.
    if (!resumeFile) {
      setClientError('Please select a PDF resume.')
      return
    }
    if (!jobDescription.trim()) {
      setClientError('Please paste the job description.')
      return
    }
    if (!companyName.trim()) {
      setClientError('Please enter the company name.')
      return
    }
    setClientError('')
    // Lift the data up to App.jsx, which will call the API.
    onSubmit(resumeFile, jobDescription, companyName)
  }

  const jdCharsLeft = MAX_JD_CHARS - jobDescription.length

  return (
    <form onSubmit={handleSubmit} className="analyze-form" noValidate>
      {/* noValidate disables browser built-in popups; we show our own messages. */}

      {clientError && (
        <div className="error-message" role="alert">
          <strong>Error: </strong>{clientError}
        </div>
      )}

      {/* htmlFor must match the input's id — that connects the label to the input
          so clicking the label focuses the input (accessibility). */}
      <div className="form-group">
        <label htmlFor="resume">📎 Resume (PDF, max {MAX_FILE_MB} MB)</label>
        <input
          id="resume"
          type="file"
          accept=".pdf,application/pdf"
          onChange={handleFileChange}
          disabled={isLoading}
          aria-describedby="resume-hint"
        />
        <span id="resume-hint" className="hint">Only PDF files are accepted.</span>
      </div>

      <div className="form-group">
        <label htmlFor="company">🏢 Company Name</label>
        <input
          id="company"
          type="text"
          value={companyName}
          onChange={e => setCompanyName(e.target.value)}
          maxLength={100}
          placeholder="e.g. Acme Corp"
          disabled={isLoading}
        />
      </div>

      <div className="form-group">
        <label htmlFor="jd">
          📋 Job Description
          {/* Character counter — turns red when near the limit */}
          <span
            className={'char-counter' + (jdCharsLeft < 200 ? ' char-counter--warn' : '')}
            aria-live="polite"
          >
            {jdCharsLeft} characters left
          </span>
        </label>
        <textarea
          id="jd"
          value={jobDescription}
          onChange={e => setJobDescription(e.target.value)}
          maxLength={MAX_JD_CHARS}
          rows={8}
          placeholder="Paste the full job description here…"
          disabled={isLoading}
        />
      </div>

      <button
        type="submit"
        className="submit-btn"
        disabled={isLoading}
        aria-busy={isLoading}
      >
        {isLoading ? '⏳ Analysing… (this can take up to a minute)' : '🚀 Analyse My Resume'}
      </button>
    </form>
  )
}
