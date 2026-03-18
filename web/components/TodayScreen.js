'use client'

import { useEffect, useState } from 'react'
import { fetchDailyPlan } from '../lib/api'
import { getSubjectColor, ls, lsSet } from '../lib/utils'

const SK_PLAN = 'nios_v2_plan'
const SK_DONE_TOPICS = 'nios_v2_done_topics'
const SK_DONE_TASKS = 'nios_v2_done_tasks'

export default function TodayScreen({ onboarding, onGoTopic }) {
    const [plan, setPlan] = useState(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [doneTasks, setDoneTasks] = useState([])

    useEffect(() => {
        const savedPlan = ls(SK_PLAN, null)
        const savedDoneTasks = ls(SK_DONE_TASKS, [])
        setDoneTasks(savedDoneTasks)

        if (savedPlan) {
            setPlan(savedPlan)
            setLoading(false)
            return
        }

        setLoading(true)
        const examMonthMap = { 'March/April': '04', 'October/November': '11' }
        const mm = examMonthMap[onboarding.examMonth] || '04'
        const examDate = `${onboarding.examYear}-${mm}-01`
        const savedDoneTopics = ls(SK_DONE_TOPICS, [])

        fetchDailyPlan({
            subjectIds: onboarding.subjectIds,
            dailyMinutes: onboarding.dailyMinutes || 60,
            goal: onboarding.goal,
            examDate,
            doneTopicIds: savedDoneTopics,
        })
            .then((p) => {
                setPlan(p)
                lsSet(SK_PLAN, p)
            })
            .catch(() => setError('Could not reach backend. Is it running?'))
            .finally(() => setLoading(false))
    }, [onboarding])

    const toggleTaskDone = (taskId) => {
        setDoneTasks((prev) => {
            const next = prev.includes(taskId)
                ? prev.filter((x) => x !== taskId)
                : [...prev, taskId]
            lsSet(SK_DONE_TASKS, next)
            return next
        })
    }

    const tasks = plan?.tasks ?? []
    const doneCount = tasks.filter((t) => doneTasks.includes(t.id)).length
    const totalMins = tasks.reduce((a, t) => a + t.estimatedMinutes, 0)
    const doneMins = tasks
        .filter((t) => doneTasks.includes(t.id))
        .reduce((a, t) => a + t.estimatedMinutes, 0)
    const pct = tasks.length ? (doneCount / tasks.length) * 100 : 0

    return (
        <div className="screen">
            <div className="today-hero">
                <div className="today-hero-label">
                    {new Date().toLocaleDateString('en-IN', {
                        weekday: 'long',
                        day: 'numeric',
                        month: 'short',
                    })}
                </div>
                <div className="today-hero-title">Today&apos;s Study Plan</div>
                <div className="today-progress-bar-wrap">
                    <div className="today-progress-bar-fill" style={{ width: `${pct}%` }} />
                </div>
                <div className="today-progress-meta">
                    <span>{doneCount}/{tasks.length} tasks done</span>
                    <span>{doneMins}/{totalMins} min</span>
                </div>
            </div>

            {error && <div className="error-text">{error}</div>}

            {loading ? (
                <div>
                    <div className="skeleton-block wide" />
                    <div className="skeleton-block med" />
                    <div className="skeleton-block wide" />
                    <div className="skeleton-block short" />
                </div>
            ) : tasks.length === 0 ? (
                <div className="empty-state">
                    <span className="empty-icon">📋</span>
                    <div className="empty-title">No tasks generated</div>
                    <div className="empty-desc">Make sure the backend is running and try again.</div>
                </div>
            ) : (
                <>
                    <div className="section-title">Tasks</div>
                    <div className="task-list">
                        {tasks.map((task) => {
                            const done = doneTasks.includes(task.id)
                            const clr = getSubjectColor(task.subjectId)
                            return (
                                <button
                                    key={task.id}
                                    className={`task-card ${done ? 'done' : ''}`}
                                    onClick={() => { if (task.topicId) onGoTopic(task.topicId) }}
                                >
                                    <div
                                        className={`task-done-check ${done ? 'checked' : ''}`}
                                        onClick={(e) => { e.stopPropagation(); toggleTaskDone(task.id) }}
                                        role="checkbox"
                                        aria-checked={done}
                                    >
                                        {done && '✓'}
                                    </div>
                                    <div className="task-card-body">
                                        <div className="task-subject-badge" style={{ color: clr }}>
                                            {task.subject}
                                        </div>
                                        <div className="task-topic-name">{task.topic}</div>
                                        <div className="task-meta-row">
                                            <span className="task-type-chip">
                                                {task.type === 'READ_NOTES' ? '📖 Notes' : '✏️ Practice'}
                                            </span>
                                            <span className="task-time-chip">~{task.estimatedMinutes} min</span>
                                        </div>
                                    </div>
                                    {task.highYieldScore >= 80 && (
                                        <div className="yield-badge">⭐ High</div>
                                    )}
                                </button>
                            )
                        })}
                    </div>
                </>
            )}
        </div>
    )
}
