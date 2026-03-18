'use client'

import { useEffect, useState } from 'react'
import { fetchTopicDetails } from '../lib/catalogApi'
import { ls, lsSet } from '../lib/utils'
import TopicPyqCard from './TopicPyqCard'

const SK_DONE_TOPICS = 'nios_v2_done_topics'

export default function TopicDetailScreen({ topicId, lang, onBack }) {
    const [details, setDetails] = useState(null)
    const [tab, setTab] = useState('notes')
    const [loadingContent, setLoadingContent] = useState(true)
    const [doneTopics, setDoneTopics] = useState([])

    useEffect(() => {
        setDoneTopics(ls(SK_DONE_TOPICS, []))
    }, [])

    const isDone = doneTopics.includes(topicId)

    const toggleDone = () => {
        setDoneTopics((prev) => {
            const next = prev.includes(topicId)
                ? prev.filter((x) => x !== topicId)
                : [...prev, topicId]
            lsSet(SK_DONE_TOPICS, next)
            return next
        })
    }

    useEffect(() => {
        setLoadingContent(true)
        setDetails(null)
        fetchTopicDetails(topicId, lang)
            .then(setDetails)
            .catch(() => { })
            .finally(() => setLoadingContent(false))
    }, [topicId, lang])

    const content = details?.content
    const pyqs = details?.pyqs ?? []

    return (
        <div className="screen">
            <div className="page-header">
                <button className="back-btn" onClick={onBack}>←</button>
                <div>
                    <div className="page-title">{content ? 'Topic Detail' : 'Loading…'}</div>
                </div>
            </div>

            {content && (
                <div className="topic-detail-hero">
                    <div className="topic-chip-row" style={{ marginBottom: '0.6rem' }}>
                        <span className="topic-chip chip-time">📖 Study topic</span>
                    </div>
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                        {content.whyImportant}
                    </p>
                </div>
            )}

            <div className="tab-bar">
                <button
                    className={`tab-btn ${tab === 'notes' ? 'active' : ''}`}
                    onClick={() => setTab('notes')}
                >
                    📝 Notes
                </button>
                <button
                    className={`tab-btn ${tab === 'pyqs' ? 'active' : ''}`}
                    onClick={() => setTab('pyqs')}
                >
                    ✏️ PYQs {pyqs.length > 0 && `(${pyqs.length})`}
                </button>
            </div>

            {tab === 'notes' && (
                <div className="notes-section">
                    {loadingContent ? (
                        <>
                            <div className="skeleton-block wide" />
                            <div className="skeleton-block med" />
                            <div className="skeleton-block wide" />
                            <div className="skeleton-block short" />
                        </>
                    ) : content ? (
                        <>
                            <div className="notes-card">
                                <div className="notes-card-label bullets">Key Points</div>
                                <ul className="bullet-list">
                                    {content.summaryBullets.map((b, i) => (
                                        <li key={i}>
                                            <div className="bullet-dot blue" />
                                            <span>{b}</span>
                                        </li>
                                    ))}
                                </ul>
                            </div>

                            <div className="notes-card">
                                <div className="notes-card-label mistakes">Common Mistakes</div>
                                <ul className="bullet-list">
                                    {content.commonMistakes.map((m, i) => (
                                        <li key={i}>
                                            <div className="bullet-dot rose" />
                                            <span>{m}</span>
                                        </li>
                                    ))}
                                </ul>
                            </div>

                            <button
                                className={`mark-done-btn ${isDone ? 'done-state' : ''}`}
                                onClick={toggleDone}
                            >
                                {isDone ? '✓ Marked as Done' : '✅ Mark as Done'}
                            </button>
                        </>
                    ) : (
                        <div className="empty-state">
                            <span className="empty-icon">📭</span>
                            <div className="empty-title">Notes not available yet</div>
                            <div className="empty-desc">Content for this topic is coming soon.</div>
                        </div>
                    )}
                </div>
            )}

            {tab === 'pyqs' && (
                <div>
                    {pyqs.length === 0 ? (
                        <div className="empty-state">
                            <span className="empty-icon">📝</span>
                            <div className="empty-title">No PYQs for this topic yet</div>
                            <div className="empty-desc">Check back as we add more question papers.</div>
                        </div>
                    ) : (
                        pyqs.map((q) => <TopicPyqCard key={q.id} pyq={q} />)
                    )}
                </div>
            )}
        </div>
    )
}
