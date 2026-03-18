'use client'

import { useEffect, useState } from 'react'
import { fetchSubjects } from '../lib/catalogApi'

const EXAM_MONTHS = ['March/April', 'October/November']
const WIZARD_STEPS = 5

const GOAL_LABELS = {
    pass: 'Just Pass',
    sixty: '60%+',
    eighty: '80%+',
}

const LANG_LABELS = {
    en: 'English',
    hi: 'Hindi',
    hinglish: 'Hinglish',
}

export default function OnboardingScreen({ onDone }) {
    const [step, setStep] = useState(0)
    const [classLevel, setClassLevel] = useState('12')
    const [subjects, setSubjects] = useState([])
    const [subjectIds, setSubjectIds] = useState([])
    const [examMonth, setExamMonth] = useState(EXAM_MONTHS[0])
    const [examYear, setExamYear] = useState(String(new Date().getFullYear()))
    const [dailyMinutes, setDailyMinutes] = useState(60)
    const [goal, setGoal] = useState('pass')
    const [language, setLanguage] = useState('hinglish')

    useEffect(() => {
        fetchSubjects(classLevel)
            .then(setSubjects)
            .catch(() => { })
    }, [classLevel])

    const toggleSubject = (id) => {
        setSubjectIds((prev) =>
            prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
        )
    }

    const canNext = () => {
        if (step === 0) return true
        if (step === 1) return subjectIds.length > 0
        if (step === 2) return !!examMonth && !!examYear
        if (step === 3) return !!dailyMinutes
        if (step === 4) return true
        return true
    }

    const next = () => {
        if (step < WIZARD_STEPS - 1) {
            setStep((s) => s + 1)
        } else {
            onDone({ classLevel, subjectIds, examMonth, examYear, dailyMinutes, goal, language })
        }
    }

    const back = () => setStep((s) => s - 1)

    return (
        <div className="onboarding-screen">
            <div className="onboarding-logo">📚</div>
            <div className="onboarding-brand">NIOS Study</div>
            <div className="onboarding-tagline">
                PYQ-based daily plans, built from official NIOS material.
            </div>

            <div className="wizard-progress">
                {Array.from({ length: WIZARD_STEPS }).map((_, i) => (
                    <div
                        key={i}
                        className={`wizard-dot ${i < step ? 'done' : i === step ? 'active' : ''}`}
                    />
                ))}
            </div>

            {step === 0 && (
                <>
                    <div className="wizard-step-label">Step 1 of {WIZARD_STEPS}</div>
                    <div className="wizard-step-title">What class are you in?</div>
                    <div className="pill-grid">
                        {['10', '12'].map((c) => (
                            <button
                                key={c}
                                className={`pill ${classLevel === c ? 'selected' : ''}`}
                                onClick={() => { setClassLevel(c); setSubjectIds([]) }}
                            >
                                Class {c}
                            </button>
                        ))}
                    </div>
                </>
            )}

            {step === 1 && (
                <>
                    <div className="wizard-step-label">Step 2 of {WIZARD_STEPS}</div>
                    <div className="wizard-step-title">Pick your subjects</div>
                    <p className="hint-text" style={{ marginBottom: '1rem' }}>
                        Select all subjects you need to study. We&apos;ll build plans for each.
                    </p>
                    <div className="pill-grid">
                        {subjects.map((s) => (
                            <button
                                key={s.id}
                                className={`pill ${subjectIds.includes(s.id) ? 'selected' : ''}`}
                                onClick={() => toggleSubject(s.id)}
                            >
                                {s.icon} {s.name}
                            </button>
                        ))}
                    </div>
                    {subjects.length === 0 && <p className="hint-text">Loading subjects…</p>}
                </>
            )}

            {step === 2 && (
                <>
                    <div className="wizard-step-label">Step 3 of {WIZARD_STEPS}</div>
                    <div className="wizard-step-title">When is your exam?</div>
                    <div className="field-group">
                        <div className="field-row">
                            <select
                                className="field-input"
                                value={examMonth}
                                onChange={(e) => setExamMonth(e.target.value)}
                            >
                                {EXAM_MONTHS.map((m) => (
                                    <option key={m} value={m}>{m}</option>
                                ))}
                            </select>
                            <input
                                className="field-input"
                                type="number"
                                placeholder="Year (e.g. 2026)"
                                value={examYear}
                                min={2025}
                                max={2035}
                                onChange={(e) => setExamYear(e.target.value)}
                            />
                        </div>
                    </div>
                </>
            )}

            {step === 3 && (
                <>
                    <div className="wizard-step-label">Step 4 of {WIZARD_STEPS}</div>
                    <div className="wizard-step-title">Time &amp; goal</div>
                    <div className="field-group">
                        <label className="field-label">Daily study time (minutes)</label>
                        <input
                            className="field-input"
                            type="number"
                            placeholder="e.g. 45"
                            value={dailyMinutes}
                            min={10}
                            max={300}
                            onChange={(e) => setDailyMinutes(e.target.value ? Number(e.target.value) : '')}
                        />
                    </div>
                    <div className="field-label" style={{ marginBottom: '0.75rem' }}>My target score</div>
                    <div className="pill-grid">
                        {Object.keys(GOAL_LABELS).map((g) => (
                            <button
                                key={g}
                                className={`pill ${goal === g ? 'selected' : ''}`}
                                onClick={() => setGoal(g)}
                            >
                                {GOAL_LABELS[g]}
                            </button>
                        ))}
                    </div>
                </>
            )}

            {step === 4 && (
                <>
                    <div className="wizard-step-label">Step 5 of {WIZARD_STEPS}</div>
                    <div className="wizard-step-title">How do you want explanations?</div>
                    <p className="hint-text" style={{ marginBottom: '1rem' }}>
                        Notes and AI explanations will be shown in your chosen language.
                    </p>
                    <div className="pill-grid">
                        {Object.keys(LANG_LABELS).map((l) => (
                            <button
                                key={l}
                                className={`pill ${language === l ? 'selected' : ''}`}
                                onClick={() => setLanguage(l)}
                            >
                                {LANG_LABELS[l]}
                            </button>
                        ))}
                    </div>
                </>
            )}

            <div className="wizard-nav">
                {step > 0 && (
                    <button className="btn-secondary" onClick={back}>← Back</button>
                )}
                <button className="btn-primary" onClick={next} disabled={!canNext()}>
                    {step === WIZARD_STEPS - 1 ? 'Start studying 🚀' : 'Continue →'}
                </button>
            </div>
        </div>
    )
}
