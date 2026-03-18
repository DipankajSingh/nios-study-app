'use client'

import { useCallback, useEffect, useState } from 'react'
import { fetchSubjects, fetchSubjectPyqs } from '../lib/catalogApi'
import { getSubjectColor } from '../lib/utils'

export default function PracticeScreen({ onboarding }) {
    const [subjects, setSubjects] = useState([])
    const [session, setSession] = useState(null)
    const [revealed, setRevealed] = useState(false)
    const [results, setResults] = useState({})

    useEffect(() => {
        fetchSubjects(onboarding.classLevel)
            .then((subs) => setSubjects(subs.filter((s) => onboarding.subjectIds.includes(s.id))))
            .catch(() => { })
    }, [onboarding])

    const startPractice = useCallback(
        async (subjectId) => {
            const allPyqs = await fetchSubjectPyqs(subjectId, onboarding.language)
            const shuffled = [...allPyqs].sort(() => Math.random() - 0.5)
            setSession({ subjectId, pyqs: shuffled, currentIndex: 0, revealed: false })
            setRevealed(false)
            setResults({})
        },
        [onboarding.language]
    )

    const current = session?.pyqs[session.currentIndex]

    const markResult = (res) => {
        if (!current || !session) return
        setResults((prev) => ({ ...prev, [current.id]: res }))
        if (session.currentIndex + 1 < session.pyqs.length) {
            setSession({ ...session, currentIndex: session.currentIndex + 1 })
            setRevealed(false)
        } else {
            setSession(null)
        }
    }

    if (!session) {
        const correctCount = Object.values(results).filter((r) => r === 'correct').length
        const total = Object.keys(results).length

        return (
            <div className="screen">
                <div className="page-header">
                    <div>
                        <div className="page-title">Practice</div>
                        <div className="page-subtitle">Past Year Questions by subject</div>
                    </div>
                </div>

                {total > 0 && (
                    <div className="today-hero" style={{ marginBottom: '1.25rem' }}>
                        <div className="today-hero-label">Session Complete 🎉</div>
                        <div className="today-hero-title">{correctCount}/{total} Correct</div>
                    </div>
                )}

                <div className="section-title">Choose a subject</div>
                <div className="practice-selector">
                    {subjects.map((s) => (
                        <button
                            key={s.id}
                            className="practice-subject-btn"
                            onClick={() => startPractice(s.id)}
                        >
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                                <span style={{ fontSize: '1.5rem' }}>{s.icon}</span>
                                <div>
                                    <div className="chapter-item-title" style={{ color: getSubjectColor(s.id) }}>
                                        {s.name}
                                    </div>
                                    <div className="chapter-item-meta">Start a PYQ session</div>
                                </div>
                            </div>
                            <span className="chevron">›</span>
                        </button>
                    ))}
                </div>
            </div>
        )
    }

    if (!current) return null

    const diffClass = `chip-diff-${current.difficulty}`
    const qNum = session.currentIndex + 1
    const total = session.pyqs.length

    return (
        <div className="screen">
            <div className="practice-header">
                <button className="back-btn" onClick={() => setSession(null)}>←</button>
                <div className="practice-counter">{qNum} / {total}</div>
            </div>

            <div className="today-progress-bar-wrap" style={{ marginBottom: '1.25rem' }}>
                <div
                    className="today-progress-bar-fill"
                    style={{ width: `${(qNum / total) * 100}%` }}
                />
            </div>

            <div className="pyq-card">
                <div className="pyq-meta-row">
                    <span className="pyq-chip chip-year">{current.year} {current.session}</span>
                    <span className="pyq-chip chip-marks">{current.marks}m</span>
                    <span className={`pyq-chip ${diffClass}`}>{current.difficulty}</span>
                </div>
                <p className="pyq-question">{current.questionText}</p>
            </div>

            {!revealed ? (
                <button className="reveal-answer-btn" onClick={() => setRevealed(true)}>
                    💡 Reveal Answer
                </button>
            ) : (
                current.explanation && (
                    <div className="answer-section">
                        {current.explanation.hints.length > 0 && (
                            <div className="hints-section" style={{ marginBottom: '0.75rem' }}>
                                <div className="answer-label">Hints</div>
                                {current.explanation.hints.map((h, i) => (
                                    <div key={i} className="hint-item">
                                        <span className="hint-bullet">💡</span>
                                        <span>{h}</span>
                                    </div>
                                ))}
                            </div>
                        )}
                        <div className="answer-label">Solution</div>
                        <ol className="step-list">
                            {current.explanation.steps.map((s, i) => (
                                <li key={i} className="step-item">
                                    <div className="step-num">{i + 1}</div>
                                    <span>{s}</span>
                                </li>
                            ))}
                        </ol>
                        {current.explanation.answer && (
                            <>
                                <div className="answer-label" style={{ marginTop: '0.75rem' }}>Answer</div>
                                <div className="answer-text">{current.explanation.answer}</div>
                            </>
                        )}
                    </div>
                )
            )}

            {revealed && (
                <div className="practice-nav-row" style={{ marginTop: '1rem' }}>
                    <button
                        className="practice-result-btn correct"
                        onClick={() => markResult('correct')}
                    >
                        ✅ Got it
                    </button>
                    <button
                        className="practice-result-btn incorrect"
                        onClick={() => markResult('incorrect')}
                    >
                        ❌ Missed it
                    </button>
                </div>
            )}
        </div>
    )
}
