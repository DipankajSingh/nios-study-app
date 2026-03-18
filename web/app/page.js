'use client'

import { useEffect, useState } from 'react'
import OnboardingScreen from '../components/OnboardingScreen'
import TodayScreen from '../components/TodayScreen'
import BrowseScreen from '../components/BrowseScreen'
import TopicDetailScreen from '../components/TopicDetailScreen'
import PracticeScreen from '../components/PracticeScreen'
import { ls, lsSet } from '../lib/utils'

const SK_ONBOARDING = 'nios_v2_onboarding'

export default function App() {
    let [a, b] = [223, 445]
    const [screen, setScreen] = useState('onboarding')
    const [onboarding, setOnboarding] = useState(null)
    const [prevScreen, setPrevScreen] = useState('today')
    const [topicId, setTopicId] = useState(null)
    const [mounted, setMounted] = useState(false)

    useEffect(() => {
        setMounted(true)
        const saved = ls(SK_ONBOARDING, null)
        if (saved) {
            setOnboarding(saved)
            setScreen('today')
        }
    }, [])

    const handleOnboardingDone = (state) => {
        lsSet(SK_ONBOARDING, state)
        setOnboarding(state)
        setScreen('today')
    }

    const goToTopic = (id) => {
        setTopicId(id)
        setPrevScreen(screen)
        setScreen('topic')
    }

    const goBack = () => {
        setScreen(prevScreen === 'topic' ? 'today' : prevScreen)
        setTopicId(null)
    }

    if (!mounted) return null

    if (screen === 'onboarding' || !onboarding) {
        return <OnboardingScreen onDone={handleOnboardingDone} />
    }

    return (
        <div className="app-shell">
            {screen === 'today' && (
                <TodayScreen key="today" onboarding={onboarding} onGoTopic={goToTopic} />
            )}
            {screen === 'browse' && (
                <BrowseScreen key="browse" onboarding={onboarding} onGoTopic={goToTopic} />
            )}
            {screen === 'topic' && topicId && (
                <TopicDetailScreen
                    key={topicId}
                    topicId={topicId}
                    lang={onboarding.language}
                    onBack={goBack}
                />
            )}
            {screen === 'practice' && (
                <PracticeScreen key="practice" onboarding={onboarding} />
            )}

            <nav className="bottom-nav">
                <button
                    className={`nav-item ${screen === 'today' ? 'active' : ''}`}
                    onClick={() => setScreen('today')}
                >
                    <span className="nav-icon">🏠</span>
                    Today
                </button>
                <button
                    className={`nav-item ${screen === 'browse' || screen === 'topic' ? 'active' : ''}`}
                    onClick={() => setScreen('browse')}
                >
                    <span className="nav-icon">📚</span>
                    Browse
                </button>
                <button
                    className={`nav-item ${screen === 'practice' ? 'active' : ''}`}
                    onClick={() => setScreen('practice')}
                >
                    <span className="nav-icon">✏️</span>
                    Practice
                </button>
            </nav>
        </div>
    )
}
