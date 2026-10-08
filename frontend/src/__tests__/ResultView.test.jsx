// Tests for ResultView.
// We give it a sample result object and assert the key parts render correctly.

import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import ResultView from '../components/ResultView.jsx'

// A minimal but complete result that matches the AnalysisResult schema.
const SAMPLE_RESULT = {
  match_score: 72,
  matched_skills: ['Python', 'FastAPI'],
  skill_gaps: [
    { skill: 'Docker', tip: 'Learn Docker by containerising one project.' },
  ],
  resume_wording_tips: ['Add "pytest" to your skills section.'],
  questions: Array.from({ length: 10 }, (_, i) => ({
    question: `Question ${i + 1}?`,
    category: 'technical',
    answer_outline: `Outline ${i + 1}`,
  })),
}

describe('ResultView', () => {
  it('renders nothing when result is null', () => {
    const { container } = render(<ResultView result={null} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('displays the match score', () => {
    render(<ResultView result={SAMPLE_RESULT} />)
    // The score number must be visible on screen
    expect(screen.getByText('72')).toBeInTheDocument()
  })

  it('displays matched skills as tags', () => {
    render(<ResultView result={SAMPLE_RESULT} />)
    expect(screen.getByText('Python')).toBeInTheDocument()
    expect(screen.getByText('FastAPI')).toBeInTheDocument()
  })

  it('displays skill gaps', () => {
    render(<ResultView result={SAMPLE_RESULT} />)
    expect(screen.getByText('Docker')).toBeInTheDocument()
    expect(screen.getByText(/containerising/i)).toBeInTheDocument()
  })

  it('displays resume wording tips when present', () => {
    render(<ResultView result={SAMPLE_RESULT} />)
    expect(screen.getByText(/pytest/i)).toBeInTheDocument()
  })

  it('hides the wording tips section when the list is empty', () => {
    const noTips = { ...SAMPLE_RESULT, resume_wording_tips: [] }
    render(<ResultView result={noTips} />)
    expect(screen.queryByText(/Resume Wording Tips/i)).not.toBeInTheDocument()
  })

  it('renders all 10 questions', () => {
    render(<ResultView result={SAMPLE_RESULT} />)
    // Each question text is "Question N?"
    expect(screen.getByText('Question 1?')).toBeInTheDocument()
    expect(screen.getByText('Question 10?')).toBeInTheDocument()
  })
})
