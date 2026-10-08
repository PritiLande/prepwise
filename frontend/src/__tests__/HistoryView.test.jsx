// Tests for HistoryView.jsx (updated for clickable cards + detail view)
//
// STRATEGY — mock api.js entirely.
//   HistoryView calls getHistory() and getAnalysisDetail().
//   We control what they return so no real HTTP requests are made.

import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import HistoryView from '../components/HistoryView.jsx'

vi.mock('../api.js', () => ({
  getHistory: vi.fn(),
  getAnalysisDetail: vi.fn(),
  MAX_JD_CHARS: 8000,
  MAX_FILE_MB: 5,
  analyzeResume: vi.fn(),
}))

import { getHistory, getAnalysisDetail } from '../api.js'

// ---------------------------------------------------------------------------
// Sample data
// ---------------------------------------------------------------------------

const FAKE_ANALYSES = [
  { id: 'uuid-1', company_name: 'Acme Corp', match_score: 72, created_at: '2026-09-01T10:00:00Z' },
  { id: 'uuid-2', company_name: 'Beta Ltd',  match_score: 55, created_at: '2026-09-02T10:00:00Z' },
]

const FAKE_DETAIL = {
  id: 'uuid-1',
  company_name: 'Acme Corp',
  match_score: 72,
  created_at: '2026-09-01T10:00:00Z',
  result_json: {
    match_score: 72,
    matched_skills: ['Python', 'FastAPI'],
    skill_gaps: [{ skill: 'Docker', tip: 'Learn Docker basics.' }],
    resume_wording_tips: [],
    questions: [],
  },
}

// A detail response that is missing resume_wording_tips (old row format)
const FAKE_DETAIL_MISSING_FIELDS = {
  id: 'uuid-1',
  company_name: 'Old Corp',
  match_score: 60,
  created_at: '2025-01-01T00:00:00Z',
  result_json: {
    match_score: 60,
    matched_skills: ['Python'],
    skill_gaps: [],
    // resume_wording_tips intentionally absent
    questions: [],
  },
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('HistoryView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading state while fetching list', () => {
    getHistory.mockReturnValue(new Promise(() => {}))
    render(<HistoryView token="fake-token" />)
    expect(screen.getByRole('status').textContent).toMatch(/loading/i)
  })

  it('renders history cards when data is returned', async () => {
    getHistory.mockResolvedValue({ analyses: FAKE_ANALYSES, total: 2 })
    render(<HistoryView token="fake-token" />)
    await waitFor(() => {
      expect(screen.getByText('Acme Corp')).toBeInTheDocument()
      expect(screen.getByText('Beta Ltd')).toBeInTheDocument()
    })
    expect(screen.getByText('72/100')).toBeInTheDocument()
  })

  it('shows empty state when no analyses exist', async () => {
    getHistory.mockResolvedValue({ analyses: [], total: 0 })
    render(<HistoryView token="fake-token" />)
    await waitFor(() => {
      expect(screen.getByText(/no saved analyses/i)).toBeInTheDocument()
    })
  })

  it('shows error message when list fetch fails', async () => {
    getHistory.mockRejectedValue(new Error('Could not retrieve history.'))
    render(<HistoryView token="fake-token" />)
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
      expect(screen.getByRole('alert').textContent).toMatch(/history/i)
    })
  })

  it('clicking a card opens the detail view', async () => {
    getHistory.mockResolvedValue({ analyses: FAKE_ANALYSES, total: 2 })
    getAnalysisDetail.mockResolvedValue(FAKE_DETAIL)

    render(<HistoryView token="fake-token" />)

    // Wait for cards to appear
    await waitFor(() => screen.getByText('Acme Corp'))

    // Click the first card
    fireEvent.click(screen.getAllByRole('button', { name: /acme corp/i })[0])

    // Detail loading state should appear
    await waitFor(() => {
      expect(getAnalysisDetail).toHaveBeenCalledWith('uuid-1', 'fake-token')
    })

    // After load, result data should be visible
    await waitFor(() => {
      expect(screen.getByText('Python')).toBeInTheDocument()
    })
  })

  it('back button returns to the list view', async () => {
    getHistory.mockResolvedValue({ analyses: FAKE_ANALYSES, total: 2 })
    getAnalysisDetail.mockResolvedValue(FAKE_DETAIL)

    render(<HistoryView token="fake-token" />)
    await waitFor(() => screen.getByText('Acme Corp'))

    // Open detail
    fireEvent.click(screen.getAllByRole('button', { name: /acme corp/i })[0])
    await waitFor(() => screen.getByText(/back to history/i))

    // Press back
    fireEvent.click(screen.getByRole('button', { name: /back to history/i }))

    // List must reappear
    await waitFor(() => {
      expect(screen.getByText('Acme Corp')).toBeInTheDocument()
      expect(screen.getByText('Beta Ltd')).toBeInTheDocument()
    })
  })

  it('shows error if detail fetch fails', async () => {
    getHistory.mockResolvedValue({ analyses: FAKE_ANALYSES, total: 2 })
    getAnalysisDetail.mockRejectedValue(new Error('Analysis not found.'))

    render(<HistoryView token="fake-token" />)
    await waitFor(() => screen.getByText('Acme Corp'))

    fireEvent.click(screen.getAllByRole('button', { name: /acme corp/i })[0])

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
      expect(screen.getByRole('alert').textContent).toMatch(/not found/i)
    })
  })

  it('renders detail with missing optional fields without crashing', async () => {
    // result_json lacks resume_wording_tips — old row format
    getHistory.mockResolvedValue({ analyses: FAKE_ANALYSES, total: 2 })
    getAnalysisDetail.mockResolvedValue(FAKE_DETAIL_MISSING_FIELDS)

    render(<HistoryView token="fake-token" />)
    await waitFor(() => screen.getByText('Acme Corp'))

    fireEvent.click(screen.getAllByRole('button', { name: /acme corp/i })[0])

    // ResultView must render without crashing — score visible, no wording tips section
    await waitFor(() => {
      expect(screen.getByText('60')).toBeInTheDocument()  // match_score
    })
    // Wording tips section must be absent (field was missing)
    expect(screen.queryByText(/resume wording tips/i)).not.toBeInTheDocument()
  })
})
