import { useState, useEffect } from 'react'
import ReviewQueue from './components/ReviewQueue'
import ComparisonView from './components/ComparisonView'
import './App.css'

function App() {
    const [currentView, setCurrentView] = useState('queue')
    const [selectedIssue, setSelectedIssue] = useState(null)
    const [stats, setStats] = useState({ critical: 0, major: 0, minor: 0, total: 0 })

    useEffect(() => {
        fetchStats()
    }, [])

    const fetchStats = async () => {
        try {
            const res = await fetch('/api/queue')
            const data = await res.json()
            const issues = data.queue || []

            setStats({
                critical: issues.filter(i => i.severity === 'CRITICAL').length,
                major: issues.filter(i => i.severity === 'MAJOR').length,
                minor: issues.filter(i => i.severity === 'MINOR').length,
                total: data.total || 0
            })
        } catch (err) {
            console.error('Failed to fetch stats:', err)
        }
    }

    const handleIssueSelect = (issue) => {
        setSelectedIssue(issue)
        setCurrentView('comparison')
    }

    const handleBack = () => {
        setSelectedIssue(null)
        setCurrentView('queue')
        fetchStats()
    }

    return (
        <div className="app">
            <header className="app-header">
                <h1>🔍 Advanced Proofing System</h1>
                <div className="stats-bar">
                    <span className="stat critical">CRITICAL: {stats.critical}</span>
                    <span className="stat major">MAJOR: {stats.major}</span>
                    <span className="stat minor">MINOR: {stats.minor}</span>
                    <span className="stat total">Total: {stats.total}</span>
                </div>
            </header>

            <main className="app-main">
                {currentView === 'queue' && (
                    <ReviewQueue onSelect={handleIssueSelect} />
                )}
                {currentView === 'comparison' && selectedIssue && (
                    <ComparisonView issue={selectedIssue} onBack={handleBack} />
                )}
            </main>
        </div>
    )
}

export default App
