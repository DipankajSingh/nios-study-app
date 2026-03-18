export function getSubjectColor(subjectId) {
    const map = {
        'maths-12': '#38bdf8',
        'english-12': '#a78bfa',
        'science-12': '#34d399',
        'sst-12': '#fbbf24',
    }
    return map[subjectId] || '#38bdf8'
}

export function getYieldColor(score) {
    if (score >= 85) return '#34d399'
    if (score >= 70) return '#fbbf24'
    return '#8da4c4'
}

export function ls(key, fallback) {
    try {
        const raw = localStorage.getItem(key)
        return raw ? JSON.parse(raw) : fallback
    } catch {
        return fallback
    }
}

export function lsSet(key, value) {
    try {
        localStorage.setItem(key, JSON.stringify(value))
    } catch {
        /* ignore */
    }
}
