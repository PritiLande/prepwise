// Tests for AnalyzeForm.
//
// WHY mock the API?
//   Tests must never make real HTTP requests — they would be slow, flaky,
//   and cost money (Groq tokens). We use vi.mock() to replace api.js with
//   a fake version that we fully control.
//
// STRATEGY: render the component, interact with it the way a user would
// (type, click), then assert what appears on screen.

import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import AnalyzeForm from '../components/AnalyzeForm.jsx'

// ── Helpers ────────────────────────────────────────────────────────

// Make a minimal fake PDF File object. The browser's File API is available
// in jsdom so we can instantiate it directly.
function makePdfFile(name = 'resume.pdf', sizeBytes = 1024) {
  const content = new Uint8Array(sizeBytes)
  return new File([content], name, { type: 'application/pdf' })
}

// ── Tests ──────────────────────────────────────────────────────────

describe('AnalyzeForm', () => {
  const onSubmit = vi.fn()   // a spy — records every call made to it

  beforeEach(() => {
    onSubmit.mockClear()     // reset the spy before each test
  })

  it('blocks submit and shows error when all fields are empty', () => {
    render(<AnalyzeForm onSubmit={onSubmit} isLoading={false} />)

    // Click the submit button without filling anything in
    fireEvent.click(screen.getByRole('button', { name: /analyse/i }))

    // The error message must appear
    expect(screen.getByRole('alert')).toBeInTheDocument()

    // onSubmit must NOT have been called
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('blocks submit and shows error when only the file is provided', async () => {
    render(<AnalyzeForm onSubmit={onSubmit} isLoading={false} />)

    // Upload a file
    const fileInput = screen.getByLabelText(/resume/i)
    await userEvent.upload(fileInput, makePdfFile())

    // Submit without filling JD or company name
    fireEvent.click(screen.getByRole('button', { name: /analyse/i }))

    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('calls onSubmit with the correct arguments when all fields are valid', async () => {
    render(<AnalyzeForm onSubmit={onSubmit} isLoading={false} />)

    const file = makePdfFile()

    // Fill in the file
    await userEvent.upload(screen.getByLabelText(/resume/i), file)

    // Fill in company name
    await userEvent.type(screen.getByLabelText(/company name/i), 'Acme Corp')

    // Fill in job description
    await userEvent.type(
      screen.getByLabelText(/job description/i),
      'We need a Python developer.'
    )

    // Submit
    fireEvent.click(screen.getByRole('button', { name: /analyse/i }))

    // onSubmit must have been called once with (file, jd, company)
    expect(onSubmit).toHaveBeenCalledOnce()
    const [calledFile, calledJd, calledCompany] = onSubmit.mock.calls[0]
    expect(calledFile.name).toBe('resume.pdf')
    expect(calledJd).toBe('We need a Python developer.')
    expect(calledCompany).toBe('Acme Corp')
  })

  it('shows error and does not submit when a non-PDF file is selected', () => {
    render(<AnalyzeForm onSubmit={onSubmit} isLoading={false} />)

    const txtFile = new File(['hello'], 'cv.txt', { type: 'text/plain' })
    const fileInput = screen.getByLabelText(/resume/i)

    // fireEvent.change fires the onChange handler synchronously in jsdom,
    // which is more reliable than userEvent.upload for file-type checks.
    fireEvent.change(fileInput, { target: { files: [txtFile] } })

    // An inline error should appear immediately after choosing the file
    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(screen.getByRole('alert').textContent).toMatch(/pdf/i)
  })

  it('disables the submit button while loading', () => {
    render(<AnalyzeForm onSubmit={onSubmit} isLoading={true} />)

    expect(screen.getByRole('button', { name: /analysing/i })).toBeDisabled()
  })
})
