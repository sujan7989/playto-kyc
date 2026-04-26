import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api'
import Navbar from '../components/Navbar'
import StateBadge from '../components/StateBadge'

export default function MerchantDashboard() {
  const [submissions, setSubmissions] = useState([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    api.get('/merchant/submissions/').then(res => setSubmissions(res.data)).finally(() => setLoading(false))
  }, [])

  const createNew = async () => {
    setCreating(true)
    try {
      const res = await api.post('/merchant/submissions/')
      navigate(`/merchant/kyc/${res.data.id}`)
    } catch (e) {
      alert('Failed to create submission')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <div className="max-w-4xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-800">My KYC Submissions</h2>
            <p className="text-gray-500 text-sm mt-1">Track your verification status</p>
          </div>
          <button onClick={createNew} disabled={creating}
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-semibold transition disabled:opacity-60">
            {creating ? 'Creating...' : '+ New Submission'}
          </button>
        </div>

        {loading ? (
          <div className="text-center py-16 text-gray-400">Loading...</div>
        ) : submissions.length === 0 ? (
          <div className="text-center py-16 bg-white rounded-xl border border-dashed border-gray-300">
            <p className="text-gray-500 mb-4">No submissions yet</p>
            <button onClick={createNew} className="bg-blue-600 text-white px-6 py-2 rounded-lg text-sm font-semibold">
              Start KYC
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {submissions.map(sub => (
              <div key={sub.id}
                onClick={() => navigate(`/merchant/kyc/${sub.id}`)}
                className="bg-white rounded-xl border border-gray-200 p-5 flex items-center justify-between cursor-pointer hover:shadow-md transition">
                <div>
                  <div className="flex items-center gap-3">
                    <span className="font-semibold text-gray-800">
                      {sub.business_name || `Submission #${sub.id}`}
                    </span>
                    <StateBadge state={sub.state} />
                    {sub.is_at_risk && (
                      <span className="text-xs bg-orange-100 text-orange-700 px-2 py-0.5 rounded-full font-semibold">
                        ⚠ At Risk
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-400 mt-1">
                    Created {new Date(sub.created_at).toLocaleDateString()}
                    {sub.submitted_at && ` · Submitted ${new Date(sub.submitted_at).toLocaleDateString()}`}
                  </p>
                </div>
                <span className="text-gray-400 text-lg">›</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
