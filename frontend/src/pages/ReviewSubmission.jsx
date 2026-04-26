import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api from '../api'
import Navbar from '../components/Navbar'
import StateBadge from '../components/StateBadge'

const TRANSITION_LABELS = {
  under_review: 'Start Review',
  approved: 'Approve',
  rejected: 'Reject',
  more_info_requested: 'Request More Info',
  submitted: 'Return to Submitted',
}

const TRANSITION_COLORS = {
  under_review: 'bg-yellow-500 hover:bg-yellow-600',
  approved: 'bg-green-600 hover:bg-green-700',
  rejected: 'bg-red-600 hover:bg-red-700',
  more_info_requested: 'bg-purple-600 hover:bg-purple-700',
  submitted: 'bg-blue-600 hover:bg-blue-700',
}

export default function ReviewSubmission() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [submission, setSubmission] = useState(null)
  const [note, setNote] = useState('')
  const [loading, setLoading] = useState(true)
  const [transitioning, setTransitioning] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    api.get(`/reviewer/submissions/${id}/`).then(res => setSubmission(res.data)).finally(() => setLoading(false))
  }, [id])

  const doTransition = async (newState) => {
    setTransitioning(true)
    setError('')
    try {
      const res = await api.post(`/reviewer/submissions/${id}/transition/`, { new_state: newState, note })
      setSubmission(res.data)
      setSuccess(`State changed to: ${newState}`)
      setNote('')
      setTimeout(() => setSuccess(''), 3000)
    } catch (e) {
      setError(e.response?.data?.detail || 'Transition failed')
    } finally {
      setTransitioning(false)
    }
  }

  if (loading) return <div className="flex items-center justify-center h-screen text-gray-400">Loading...</div>
  if (!submission) return null

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <div className="max-w-3xl mx-auto px-4 py-8">
        <button onClick={() => navigate('/reviewer')} className="text-blue-600 text-sm hover:underline mb-4 block">← Back to Dashboard</button>

        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-gray-800">Submission #{id}</h2>
          <div className="flex items-center gap-3">
            <StateBadge state={submission.state} />
            {submission.is_at_risk && (
              <span className="text-xs bg-red-100 text-red-700 px-2 py-1 rounded-full font-semibold">⚠ SLA At Risk</span>
            )}
          </div>
        </div>

        {error && <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 mb-4 text-sm">{error}</div>}
        {success && <div className="bg-green-50 border border-green-200 text-green-700 rounded-lg px-4 py-3 mb-4 text-sm">{success}</div>}

        {/* Details */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <InfoCard title="Personal Details">
            <InfoRow label="Name" value={submission.full_name} />
            <InfoRow label="Email" value={submission.email} />
            <InfoRow label="Phone" value={submission.phone} />
          </InfoCard>
          <InfoCard title="Business Details">
            <InfoRow label="Business" value={submission.business_name} />
            <InfoRow label="Type" value={submission.business_type} />
            <InfoRow label="Monthly Volume" value={submission.expected_monthly_volume ? `$${submission.expected_monthly_volume}` : ''} />
          </InfoCard>
        </div>

        {/* Timeline */}
        <InfoCard title="Timeline" className="mb-4">
          <InfoRow label="Created" value={submission.created_at ? new Date(submission.created_at).toLocaleString() : '—'} />
          <InfoRow label="Submitted" value={submission.submitted_at ? new Date(submission.submitted_at).toLocaleString() : '—'} />
          <InfoRow label="Reviewed" value={submission.reviewed_at ? new Date(submission.reviewed_at).toLocaleString() : '—'} />
          <InfoRow label="Reviewer" value={submission.reviewer_username || '—'} />
          {submission.time_in_queue_hours != null && (
            <InfoRow label="Time in Queue" value={`${submission.time_in_queue_hours} hours`} />
          )}
        </InfoCard>

        {/* Documents */}
        <InfoCard title="Documents" className="mb-4">
          {submission.documents?.length === 0 ? (
            <p className="text-gray-400 text-sm">No documents uploaded</p>
          ) : (
            submission.documents?.map(doc => (
              <div key={doc.id} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                <div>
                  <span className="text-sm font-medium text-gray-700 capitalize">{doc.doc_type.replace('_', ' ')}</span>
                  <span className="text-xs text-gray-400 ml-2">{doc.original_filename} · {(doc.file_size / 1024).toFixed(1)} KB</span>
                </div>
                {doc.file_url && (
                  <a href={doc.file_url} target="_blank" rel="noreferrer"
                    className="text-xs text-blue-600 hover:underline font-medium">View</a>
                )}
              </div>
            ))
          )}
        </InfoCard>

        {/* Previous reviewer note */}
        {submission.reviewer_note && (
          <div className="bg-purple-50 border border-purple-200 rounded-lg p-4 mb-4 text-sm text-purple-800">
            <strong>Previous note:</strong> {submission.reviewer_note}
          </div>
        )}

        {/* Actions */}
        {submission.allowed_transitions?.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h3 className="font-semibold text-gray-800 mb-3">Take Action</h3>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">Note (optional)</label>
              <textarea value={note} onChange={e => setNote(e.target.value)} rows={3}
                placeholder="Add a note for the merchant..."
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none" />
            </div>
            <div className="flex flex-wrap gap-3">
              {submission.allowed_transitions.map(t => (
                <button key={t} onClick={() => doTransition(t)} disabled={transitioning}
                  className={`px-4 py-2 text-white text-sm font-semibold rounded-lg transition disabled:opacity-60 ${TRANSITION_COLORS[t] || 'bg-gray-500 hover:bg-gray-600'}`}>
                  {transitioning ? '...' : TRANSITION_LABELS[t] || t}
                </button>
              ))}
            </div>
          </div>
        )}

        {submission.allowed_transitions?.length === 0 && (
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-sm text-gray-500 text-center">
            This submission is in a terminal state ({submission.state}) — no further actions available.
          </div>
        )}
      </div>
    </div>
  )
}

function InfoCard({ title, children, className = '' }) {
  return (
    <div className={`bg-white rounded-xl border border-gray-200 p-5 ${className}`}>
      <h3 className="font-semibold text-gray-700 mb-3 text-sm uppercase tracking-wide">{title}</h3>
      {children}
    </div>
  )
}

function InfoRow({ label, value }) {
  return (
    <div className="flex justify-between py-1.5 border-b border-gray-50 last:border-0 text-sm">
      <span className="text-gray-500">{label}</span>
      <span className="font-medium text-gray-800">{value || <span className="text-gray-300">—</span>}</span>
    </div>
  )
}
