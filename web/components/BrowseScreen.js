'use client'

import { useEffect, useState } from 'react'
import { fetchSubjects, fetchSyllabus } from '../lib/catalogApi'
import { getSubjectColor, getYieldColor } from '../lib/utils'

export default function BrowseScreen({ onboarding, onGoTopic }) {
    const [view, setView] = useState('subjects')
    const [allSubjects, setAllSubjects] = useState([])
    const [syllabus, setSyllabus] = useState(null)
    const [selectedChapter, setSelectedChapter] = useState(null)

    useEffect(() => {
        fetchSubjects(onboarding.classLevel)
            .then((subs) => {
                const enrolled = subs.filter((s) => onboarding.subjectIds.includes(s.id))
                setAllSubjects(enrolled.length > 0 ? enrolled : subs)
            })
            .catch(() => { })
    }, [onboarding])

    const pickSubject = async (sub) => {
        const data = await fetchSyllabus(sub.id)
        setSyllabus(data)
        setView('chapters')
    }

    const pickChapter = (chap) => {
        setSelectedChapter(chap)
        setView('topics')
    }

    const goBack = () => {
        if (view === 'topics') setView('chapters')
        else if (view === 'chapters') setView('subjects')
    }

    return (
        <div className="screen">
            <div className="page-header">
                {view !== 'subjects' && (
                    <button className="back-btn" onClick={goBack}>←</button>
                )}
                <div>
                    <div className="page-title">
                        {view === 'subjects'
                            ? 'Browse'
                            : view === 'chapters'
                                ? (syllabus?.subject.name ?? 'Chapters')
                                : (selectedChapter?.title ?? 'Topics')}
                    </div>
                    {view === 'subjects' && (
                        <div className="page-subtitle">Your enrolled subjects</div>
                    )}
                </div>
            </div>

            {view === 'subjects' && (
                <div className="subject-grid">
                    {allSubjects.map((sub) => (
                        <button
                            key={sub.id}
                            className="subject-card"
                            onClick={() => pickSubject(sub)}
                            style={{ borderTopColor: getSubjectColor(sub.id), borderTopWidth: '3px' }}
                        >
                            <span className="subject-card-icon">{sub.icon}</span>
                            <div className="subject-card-name">{sub.name}</div>
                            <div className="subject-card-desc">{sub.description}</div>
                        </button>
                    ))}
                </div>
            )}

            {view === 'chapters' && syllabus && (
                <div className="chapter-list">
                    {syllabus.chapters.map((chap) => (
                        <button
                            key={chap.id}
                            className="chapter-item"
                            onClick={() => pickChapter(chap)}
                        >
                            <div>
                                <div className="chapter-item-title">{chap.title}</div>
                                <div className="chapter-item-meta">Chapter {chap.orderIndex}</div>
                            </div>
                            <span className="chevron">›</span>
                        </button>
                    ))}
                </div>
            )}

            {view === 'topics' && selectedChapter && (
                <div className="topics-list">
                    {selectedChapter.topics.map((topic) => (
                        <button
                            key={topic.id}
                            className="topic-item"
                            onClick={() => onGoTopic(topic.id)}
                            style={topic.hasContent === false ? { opacity: 0.5 } : {}}
                        >
                            <div
                                className="topic-yield-bar"
                                style={{ background: getYieldColor(topic.highYieldScore) }}
                            />
                            <div className="topic-item-body">
                                <div className="topic-item-title">{topic.title}</div>
                                <div className="topic-item-meta">
                                    <span>⭐ {topic.highYieldScore}% yield</span>
                                    <span>· ~{topic.estMinutes} min</span>
                                </div>
                            </div>
                            <span className="chevron">›</span>
                        </button>
                    ))}
                    {selectedChapter.topics.length === 0 && (
                        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>No topics found.</p>
                    )}
                </div>
            )}
        </div>
    )
}
