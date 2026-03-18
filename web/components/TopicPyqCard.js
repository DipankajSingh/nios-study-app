'use client'

import { useState } from 'react'

export default function TopicPyqCard({ pyq }) {
    const [revealed, setRevealed] = useState(false)
    const diffClass = `chip-diff-${pyq.difficulty}`

    return (
        <div className="pyq-card" style={{ marginBottom: '0.875rem' }}>
            <div className="pyq-meta-row">
                <span className="pyq-chip chip-year">{pyq.year} {pyq.session}</span>
                <span className="pyq-chip chip-marks">{pyq.marks}m</span>
                <span className={`pyq-chip ${diffClass}`}>{pyq.difficulty}</span>
            </div>
            <p className="pyq-question">{pyq.questionText}</p>

            {!revealed && (
                <button
                    className="reveal-answer-btn"
                    style={{ marginTop: '0.875rem' }}
                    onClick={() => setRevealed(true)}
                >
                    Show Answer &amp; Explanation
                </button>
            )}

            {revealed && pyq.explanation && (
                <div className="answer-section" style={{ marginTop: '0.875rem' }}>
                    {pyq.explanation.hints.length > 0 && (
                        <div className="hints-section" style={{ marginBottom: '0.75rem' }}>
                            <div className="answer-label">Hints</div>
                            {pyq.explanation.hints.map((h, i) => (
                                <div key={i} className="hint-item">
                                    <span className="hint-bullet">💡</span>
                                    <span>{h}</span>
                                </div>
                            ))}
                        </div>
                    )}
                    <div className="answer-label">Step-by-Step</div>
                    <ol className="step-list">
                        {pyq.explanation.steps.map((s, i) => (
                            <li key={i} className="step-item">
                                <div className="step-num">{i + 1}</div>
                                <span>{s}</span>
                            </li>
                        ))}
                    </ol>
                    {pyq.explanation.answer && (
                        <>
                            <div className="answer-label" style={{ marginTop: '0.75rem' }}>Answer</div>
                            <div className="answer-text">{pyq.explanation.answer}</div>
                        </>
                    )}
                </div>
            )}
        </div>
    )
}
