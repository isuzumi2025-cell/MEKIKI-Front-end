import { useState } from 'react'

function ComparisonView({ issue, onBack }) {
    const [status, setStatus] = useState(issue.status || 'OPEN')
    const [comment, setComment] = useState(issue.comment || '')
    const [overlayOpacity, setOverlayOpacity] = useState(0.5)
    const [saving, setSaving] = useState(false)

    const handleStatusChange = async (newStatus) => {
        setSaving(true)
        try {
            await fetch(`/api/issues/${issue.issue_id}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: newStatus, comment })
            })
            setStatus(newStatus)
        } catch (err) {
            console.error('Failed to update status:', err)
        } finally {
            setSaving(false)
        }
    }

    const handleSaveFeedback = async () => {
        setSaving(true)
        try {
            await fetch('/api/dataset/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    issue_id: issue.issue_id,
                    left_text: issue.left_text_norm,
                    right_text: issue.right_text_norm,
                    user_verdict: status,
                    comment
                })
            })
            alert('Feedback saved!')
        } catch (err) {
            console.error('Failed to save feedback:', err)
        } finally {
            setSaving(false)
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

    return (
        <div className="comparison-view">
            <div className="comparison-header">
                <button className="back-btn" onClick={onBack}>← Back to Queue</button>
                <h2>Issue Detail</h2>
                <span className={`severity-badge ${getSeverityClass(issue.severity)}`}>
                    {issue.severity}
                </span>
            </div>

            <div className="comparison-content">
                {/* Left Panel */}
                <div className="panel left-panel">
                    <h3>📄 Left (Reference)</h3>
                    <div className="text-box">
                        {issue.left_text_norm || '(empty)'}
                    </div>
                    {issue.evidence_left_crop && (
                        <img src={issue.evidence_left_crop} alt="Left crop" className="evidence-img" />
                    )}
                </div>

                {/* Center - Diff */}
                <div className="panel diff-panel">
                    <h3>🔄 Diff</h3>
                    <div
                        className="diff-html"
                        dangerouslySetInnerHTML={{ __html: issue.diff_html || 'No diff available' }}
                    />

                    <div className="risk-reasons">
                        <h4>Risk Reasons:</h4>
                        <ul>
                            {(issue.risk_reason || []).map((reason, i) => (
                                <li key={i}>{reason}</li>
                            ))}
                        </ul>
                    </div>

                    {issue.field_types && issue.field_types.length > 0 && (
                        <div className="field-types">
                            <h4>Fields:</h4>
                            <div className="tags">
                                {issue.field_types.map((type, i) => (
                                    <span key={i} className="tag">{type}</span>
                                ))}
                            </div>
                        </div>
                    )}
                </div>

                {/* Right Panel */}
                <div className="panel right-panel">
                    <h3>📄 Right (Target)</h3>
                    <div className="text-box">
                        {issue.right_text_norm || '(empty)'}
                    </div>
                    {issue.evidence_right_crop && (
                        <img src={issue.evidence_right_crop} alt="Right crop" className="evidence-img" />
                    )}
                </div>
            </div>

            {/* Overlay Control */}
            {issue.evidence_overlay && (
                <div className="overlay-section">
                    <h3>🔲 Overlay</h3>
                    <div className="opacity-control">
                        <label>Opacity: {(overlayOpacity * 100).toFixed(0)}%</label>
                        <input
                            type="range"
                            min="0"
                            max="1"
                            step="0.1"
                            value={overlayOpacity}
                            onChange={(e) => setOverlayOpacity(parseFloat(e.target.value))}
                        />
                    </div>
                    <img
                        src={issue.evidence_overlay}
                        alt="Overlay"
                        className="overlay-img"
                        style={{ opacity: overlayOpacity }}
                    />
                </div>
            )}

            {/* Actions */}
            <div className="actions-section">
                <h3>Actions</h3>

                <div className="status-buttons">
                    <button
                        className={`status-btn ${status === 'CONFIRMED' ? 'active' : ''}`}
                        onClick={() => handleStatusChange('CONFIRMED')}
                        disabled={saving}
                    >
                        ✅ Confirm Issue
                    </button>
                    <button
                        className={`status-btn ${status === 'RESOLVED' ? 'active' : ''}`}
                        onClick={() => handleStatusChange('RESOLVED')}
                        disabled={saving}
                    >
                        ✓ Mark Resolved
                    </button>
                    <button
                        className={`status-btn ${status === 'IGNORED' ? 'active' : ''}`}
                        onClick={() => handleStatusChange('IGNORED')}
                        disabled={saving}
                    >
                        ✕ Ignore
                    </button>
                </div>

                <div className="comment-section">
                    <label>Comment:</label>
                    <textarea
                        value={comment}
                        onChange={(e) => setComment(e.target.value)}
                        placeholder="Add your notes here..."
                        rows={3}
                    />
                </div>

                <button
                    className="save-feedback-btn"
                    onClick={handleSaveFeedback}
                    disabled={saving}
                >
                    💾 Save Feedback (Training Data)
                </button>
            </div>
        </div>
    )
}

export default ComparisonView
