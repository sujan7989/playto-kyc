import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api'
import Navbar from '../components/Navbar'
import StateBadge from '../components/StateBadge'

export default function ReviewerDashboard() {
  const [metrics, setMetrics] = useState(null)
  const [queue, setQueue] = useState([])
  const [allSubs, setAllSubs] = useState([])
  const [tab, setTab] = useState('queue')
  const [stateFilter, setStateFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    Promise.all([
      api.get('/reviewer/dashboard/metrics/'),
      api.get('/reviewer/queue/'),
      api.get('/reviewer/submissions/'),
    ]).then(([m, q, a]) => {
      setMetrics(m.data)
      setQueue(q.data)
      setAllSubs(a.data)
    }).finally(() => setLoading(false))
  }, [])

  const filtered = stateFilter ? allSubs.filter(s => s.state === stateFilter) : allSubs

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <div className="max-w-5xl mx-auto px-4 py-8">
        <h2 className="text-2xl font-bold text-gray-800 mb-6">Reviewer Dashboard</h2>

        {/* Metrics */}
        {metrics && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <MetricCard label="In Queue" value={metrics.submissions_in_queue} color="blue" />
            <MetricCard label="Avg Time in Queue" value={`${metrics.average_time_in_queue_hours}h`} color="yellow" />
            <MetricCard label="Approval Rate (7d)" value={`${metrics.approval_rate_last_7_days}%`} color="green" />
            <MetricCard label="At Risk" value={metrics.at_risk_count} color="red" />
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-2 mb-4">
          <TabBtn active={tab === 'queue'} onClick={() => setTab('queue')}>
            Queue ({queue.length})
          </TabBtn>
          <TabBtn active={tab === 'all'} onClick={() => setTab('all')}>
            All Submissions
          </TabBtn>
        </div>

        {tab === 'all' && (
          <div className="mb-4">
            <select value={stateFilter} onChange={e => setStateFilter(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
              <option value="">All States</option>
              <option value="draft">Draft</option>
              <option value="submitted">Submitted</option>
              <option value="under_review">Under Review</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
              <option value="more_info_requested">More Info Requested</option>
            </select>
          </div>
        )}

        {loading ? (
          <div className="text-center py-16 text-gray-400">Loading...</div>
        ) : (
          <SubmissionTable
            submissions={tab === 'queue' ? queue : filtered}
            onSelect={id => navigate(`/reviewer/submission/${id}`)}
          />
        )}
      </div>
    </div>
  )
}

function MetricCard({ label, value, color }) {
  const colors = {
    blue: 'bg-blue-50 border-blue-200 text-blue-700',
    yellow: 'bg-yellow-50 border-yellow-200 text-yellow-700',
    green: 'bg-green-50 border-green-200 text-green-700',
    red: 'bg-red-50 border-red-200 text-red-700',
  }
  return (
    <div className={`rounded-xl border p-4 ${colors[color]}`}>
      <p className="text-xs font-medium opacity-70 mb-1">{label}</p>
      <p className="text-2xl font-bold">{value}</p>
    </div>
  )
}

function TabBtn({ active, onClick, children }) {
  return (
    <button onClick={onClick}
      className={`px-4 py-2 rounded-lg text-sm font-medium transition ${active ? 'bg-blue-600 text-white' : 'bg-white border border-gray-300 text-gray-600 hover:bg-gray-50'}`}>
      {children}
    </button>
  )
}

function SubmissionTable({ submissions, onSelect }) {
  if (submissions.length === 0) {
    return <div className="text-center py-16 text-gray-400 bg-white rounded-xl border border-dashed border-gray-300">No submissions found</div>
  }
  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 border-b border-gray-200">
          <tr>
            <th className="text-left px-4 py-3 text-gray-600 font-semibold">#</th>
            <th className="text-left px-4 py-3 text-gray-600 font-semibold">Merchant</th>
            <th className="text-left px-4 py-3 text-gray-600 font-semibold">Business</th>
            <th className="text-left px-4 py-3 text-gray-600 font-semibold">State</th>
            <th className="text-left px-4 py-3 text-gray-600 font-semibold">Submitted</th>
            <th className="text-left px-4 py-3 text-gray-600 font-semibold">SLA</th>
          </tr>
        </thead>
        <tbody>
          {submissions.map(sub => (
            <tr key={sub.id} onClick={() => onSelect(sub.id)}
              className="border-b border-gray-100 hover:bg-blue-50 cursor-pointer transition">
              <td className="px-4 py-3 text-gray-500">{sub.id}</td>
              <td className="px-4 py-3 font-medium text-gray-800">{sub.merchant_username}</td>
              <td className="px-4 py-3 text-gray-600">{sub.business_name || '—'}</td>
              <td className="px-4 py-3"><StateBadge state={sub.state} /></td>
              <td className="px-4 py-3 text-gray-500">
                {sub.submitted_at ? new Date(sub.submitted_at).toLocaleDateString() : '—'}
              </td>
              <td className="px-4 py-3">
                {sub.is_at_risk ? (
                  <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full font-semibold">⚠ At Risk</span>
                ) : sub.time_in_queue_hours != null ? (
                  <span className="text-xs text-gray-500">{sub.time_in_queue_hours}h</span>
                ) : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
