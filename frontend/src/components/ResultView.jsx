// ResultView — displays the full analysis returned by the backend.
// WHY separate from App? This component only knows how to DISPLAY data.
// App knows how to FETCH data. Mixing them would make both harder to read.
//
// DEFENSIVE RENDERING: old rows saved before recent prompt changes may lack
// some fields (e.g. resume_wording_tips absent, questions array empty).
// Every field is defaulted so the component never crashes on missing data.

export default function ResultView({ result }) {
  if (!result) return null

  // Destructure with defaults so missing fields from old rows don't crash.
  // If result_json is nested (from the detail endpoint), unwrap it first.
  const data = result.result_json ?? result

  const match_score        = data.match_score        ?? 0
  const matched_skills     = data.matched_skills      ?? []
  const skill_gaps         = data.skill_gaps          ?? []
  const resume_wording_tips= data.resume_wording_tips ?? []
  const questions          = data.questions           ?? []

  return (
    <div className="result-view">

      {/* ── Match Score ─────────────────────────────────────────── */}
      <section className="result-section" aria-labelledby="score-heading">
        <h2 id="score-heading">🎯 Match Score</h2>
        <div className="score-display">
          <span className="score-number">{match_score}</span>
          <span className="score-denom">/100</span>
        </div>
        <div className="score-bar-track" role="progressbar"
             aria-valuenow={match_score} aria-valuemin={0} aria-valuemax={100}
             aria-label={`Match score: ${match_score} out of 100`}>
          <div className="score-bar-fill" style={{ width: `${match_score}%` }} />
        </div>
      </section>

      {/* ── Matched Skills ──────────────────────────────────────── */}
      <section className="result-section" aria-labelledby="matched-heading">
        <h2 id="matched-heading">✅ Matched Skills</h2>
        {matched_skills.length === 0 ? (
          <p>No direct skill matches found.</p>
        ) : (
          <ul className="tag-list">
            {matched_skills.map(skill => (
              <li key={skill} className="tag tag--match">{skill}</li>
            ))}
          </ul>
        )}
      </section>

      {/* ── Skill Gaps ──────────────────────────────────────────── */}
      <section className="result-section" aria-labelledby="gaps-heading">
        <h2 id="gaps-heading">⚠️ Skill Gaps</h2>
        {skill_gaps.length === 0 ? (
          <p>No significant skill gaps found — great match!</p>
        ) : (
          <ul className="gap-list">
            {skill_gaps.map(gap => (
              <li key={gap.skill} className="gap-item">
                <strong>{gap.skill}</strong>
                <p>{gap.tip}</p>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* ── Resume Wording Tips — hidden if empty or absent ─────── */}
      {resume_wording_tips.length > 0 && (
        <section className="result-section" aria-labelledby="tips-heading">
          <h2 id="tips-heading">💡 Resume Wording Tips</h2>
          <p className="section-hint">
            These skills are visible in your resume but not named — adding the
            keyword helps ATS scanners find them.
          </p>
          <ul className="tip-list">
            {resume_wording_tips.map((tip, i) => (
              <li key={i}>{tip}</li>
            ))}
          </ul>
        </section>
      )}

      {/* ── Interview Questions ─────────────────────────────────── */}
      {questions.length > 0 && (
        <section className="result-section" aria-labelledby="questions-heading">
          <h2 id="questions-heading">🎤 Interview Questions</h2>
          <ol className="question-list">
            {questions.map((q, i) => (
              <li key={i} className="question-item">
                <span className={`category-badge category-badge--${q.category}`}>
                  {q.category}
                </span>
                <p className="question-text">{q.question}</p>
                <details className="answer-details">
                  <summary>Show answer outline</summary>
                  <p className="answer-outline">{q.answer_outline}</p>
                </details>
              </li>
            ))}
          </ol>
        </section>
      )}

    </div>
  )
}
