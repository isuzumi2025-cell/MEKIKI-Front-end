import { useState, useEffect } from 'react'

function ReviewQueue({ onSelect }) {
    const [issues, setIssues] = useState([])
    const [loading, setLoading] = useState(true)
    const [filter, setFilter] = useState('all')

    useEffect(() => {
        fetchQueue()
    }, [filter])

    const fetchQueue = async () => {
        setLoading(true)
        try {
            let url = '/api/queue?limit=100'
            if (filter !== 'all') {
                url = `/api/issues?severity=${filter}&status=OPEN&limit=100`
            }

            const res = await fetch(url)
            const data = await res.json()
            setIssues(data.queue || data.issues || [])
        } catch (err) {
            console.error('Failed to fetch queue:', err)
        } finally {
            setLoading(false)
        }
    }

    const getSeverityClass = (severity) => {
        switch (severity) {
            case 'CRITICAL': return 'severity-critical'
            case 'MAJOR': return 'severity-major'
            case 'MINOR': return 'severity-minor'
            default: return 'severity-info'
        }
    }

    const truncate = (text, len = 50) => {
        if (!text) return ''
        return text.length > len ? text.slice(0, len) + '...' : text
    }

    return (
        <div className="review-queue">
            <div className="queue-header">
                <h2>📋 Review Queue</h2>
                <div className="filter-buttons">
                    <button
                        className={filter === 'all' ? 'active' : ''}
                        onClick={() => setFilter('all')}
                    >
                        All
                    </button>
                    <button
                        className={filter === 'CRITICAL' ? 'active critical' : ''}
                        onClick={() => setFilter('CRITICAL')}
                    >
                        CRITICAL
                    </button>
                    <button
                        className={filter === 'MAJOR' ? 'active major' : ''}
                        onClick={() => setFilter('MAJOR')}
                    >
                        MAJOR
                    </button>
                    <button
                        className={filter === 'MINOR' ? 'active minor' : ''}
                        onClick={() => setFilter('MINOR')}
                    >
                        MINOR
                    </button>
                </div>
            </div>

            {loading ? (
                <div className="loading">Loading...</div>
            ) : issues.length === 0 ? (
                <div className="empty-queue">
                    <p>🎉 No issues to review!</p>
                </div>
            ) : (
                <table className="queue-table">
                    <thead>
                        <tr>
                            <th>Severity</th>
                            <th>Type</th>
                            <th>Left Text</th>
                            <th>Right Text</th>
                            <th>Risk Reason</th>
                            <th>Score</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {issues.map((issue) => (
                            <tr key={issue.issue_id} className={getSeverityClass(issue.severity)}>
                                <td>
                                    <span className={`severity-badge ${getSeverityClass(issue.severity)}`}>
                                        {issue.severity}
                                    </span>
                                </td>
                                <td>{issue.diff_type}</td>
                                <td title={issue.left_text_norm}>{truncate(issue.left_text_norm)}</td>
                                <td title={issue.right_text_norm}>{truncate(issue.right_text_norm)}</td>
                                <td>{(issue.risk_reason || []).join(', ')}</td>
                                <td>{(issue.score_total * 100).toFixed(0)}%</td>
                                <td>
                                    <button
                                        className="view-btn"
                                        onClick={() => onSelect(issue)}
                                    >
                                        View
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            )}
        </div>
    )
}

export default ReviewQueue
