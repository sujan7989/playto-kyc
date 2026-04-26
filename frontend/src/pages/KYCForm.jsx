import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api from '../api'
import Navbar from '../components/Navbar'
import StateBadge from '../components/StateBadge'

const STEPS = ['Personal Details', 'Business Details', 'Documents', 'Review & Submit']

export default function KYCForm() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [submission, setSubmission] = useState(null)
  const [form, setForm] = useState({ full_name: '', email: '', phone: '', business_name: '', business_type: '', expected_monthly_volume: '' })
  const [docs, setDocs] = useState({ pan: null, aadhaar: null, bank_statement: null })
  const [uploadedDocs, setUploadedDocs] = useState({})
  const [saving, setSaving] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const editable = submission && ['draft', 'more_info_requested'].includes(submission.state)

  useEffect(() => {
    api.get(`/merchant/submissions/${id}/`).then(res => {
      setSubmission(res.data)
      setForm({
        full_name: res.data.full_name || '',
        email: res.data.email || '',
        phone: res.data.phone || '',
        business_name: res.data.business_name || '',
        business_type: res.data.business_type || '',
        expected_monthly_volume: res.data.expected_monthly_volume || '',
      })
      const uploaded = {}
      res.data.documents?.forEach(d => { uploaded[d.doc_type] = d })
      setUploadedDocs(uploaded)
    }).catch(() => navigate('/merchant'))
  }, [id])

  const saveProgress = async () => {
    if (!editable) return
    setSaving(true)
    setError('')
    try {
      const res = await api.patch(`/merchant/submissions/${id}/`, form)
      setSubmission(res.data)
      setSuccess('Progress saved!')
      setTimeout(() => setSuccess(''), 2000)
    } catch (e) {
      setError(e.response?.data?.detail || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const uploadDoc = async (docType, file) => {
    if (!file) return
    const data = new FormData()
    data.append('doc_type', docType)
    data.append('file', file)
    setError('')
    try {
      const res = await api.post(`/merchant/submissions/${id}/documents/`, data, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      setUploadedDocs(prev => ({ ...prev, [docType]: res.data }))
      setSuccess(`${docType.replace('_', ' ')} uploaded!`)
      setTimeout(() => setSuccess(''), 2000)
    } catch (e) {
      const detail = e.response?.data?.detail
      setError(typeof detail === 'object' ? JSON.stringify(detail) : detail || 'Upload failed')
    }
  }

  const handleSubmit = async () => {
    setSubmitting(true)
    setError('')
    try {
      await saveProgress()
      const res = await api.post(`/merchant/submissions/${id}/submit/`)
      setSubmission(res.data)
      setSuccess('KYC submitted successfully!')
    } catch (e) {
      setError(e.response?.data?.detail || 'Submission failed')
    } finally {
      setSubmitting(false)
    }
  }

  if (!submission) return <div className="flex items-center justify-center h-screen text-gray-400">Loading...</div>

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <div className="max-w-2xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <button onClick={() => navigate('/merchant')} className="text-blue-600 text-sm hover:underline mb-1 block">← Back</button>
            <h2 className="text-xl font-bold text-gray-800">KYC Submission #{id}</h2>
          </div>
          <StateBadge state={submission.state} />
        </div>

        {/* Reviewer note */}
        {submission.reviewer_note && (
          <div className="bg-purple-50 border border-purple-200 rounded-lg p-4 mb-4 text-sm text-purple-800">
            <strong>Reviewer note:</strong> {submission.reviewer_note}
          </div>
        )}

        {/* Alerts */}
        {error && <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 mb-4 text-sm">{error}</div>}
        {success && <div className="bg-green-50 border border-green-200 text-green-700 rounded-lg px-4 py-3 mb-4 text-sm">{success}</div>}

        {/* Step indicator */}
        <div className="flex items-center mb-8">
          {STEPS.map((s, i) => (
            <div key={i} className="flex items-center flex-1">
              <button onClick={() => setStep(i)}
                className={`w-8 h-8 rounded-full text-sm font-bold flex items-center justify-center transition
                  ${i === step ? 'bg-blue-600 text-white' : i < step ? 'bg-green-500 text-white' : 'bg-gray-200 text-gray-500'}`}>
                {i < step ? '✓' : i + 1}
              </button>
              {i < STEPS.length - 1 && <div className={`flex-1 h-1 mx-1 ${i < step ? 'bg-green-400' : 'bg-gray-200'}`} />}
            </div>
          ))}
        </div>
        <p className="text-center text-sm font-medium text-gray-600 mb-6">{STEPS[step]}</p>

        <div className="bg-white rounded-xl border border-gray-200 p-6">
          {/* Step 0: Personal */}
          {step === 0 && (
            <div className="space-y-4">
              <Field label="Full Name" value={form.full_name} disabled={!editable}
                onChange={v => setForm({ ...form, full_name: v })} />
              <Field label="Email" type="email" value={form.email} disabled={!editable}
                onChange={v => setForm({ ...form, email: v })} />
              <Field label="Phone" value={form.phone} disabled={!editable}
                onChange={v => setForm({ ...form, phone: v })} placeholder="+91-9876543210" />
            </div>
          )}

          {/* Step 1: Business */}
          {step === 1 && (
            <div className="space-y-4">
              <Field label="Business Name" value={form.business_name} disabled={!editable}
                onChange={v => setForm({ ...form, business_name: v })} />
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Business Type</label>
                <select value={form.business_type} disabled={!editable}
                  onChange={e => setForm({ ...form, business_type: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50">
                  <option value="">Select type</option>
                  <option value="freelancer">Freelancer</option>
                  <option value="agency">Agency</option>
                  <option value="ecommerce">E-Commerce</option>
                  <option value="saas">SaaS</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <Field label="Expected Monthly Volume (USD)" type="number" value={form.expected_monthly_volume}
                disabled={!editable} onChange={v => setForm({ ...form, expected_monthly_volume: v })} placeholder="5000" />
            </div>
          )}

          {/* Step 2: Documents */}
          {step === 2 && (
            <div className="space-y-5">
              {[
                { key: 'pan', label: 'PAN Card' },
                { key: 'aadhaar', label: 'Aadhaar Card' },
                { key: 'bank_statement', label: 'Bank Statement' },
              ].map(({ key, label }) => (
                <div key={key} className="border border-gray-200 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-gray-700">{label}</span>
                    {uploadedDocs[key] && (
                      <span className="text-xs text-green-600 font-semibold">✓ Uploaded: {uploadedDocs[key].original_filename}</span>
                    )}
                  </div>
                  {editable && (
                    <div>
                      <input type="file" accept=".pdf,.jpg,.jpeg,.png"
                        onChange={e => {
                          const file = e.target.files[0]
                          if (file) uploadDoc(key, file)
                        }}
                        className="text-sm text-gray-500 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-sm file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100" />
                      <p className="text-xs text-gray-400 mt-1">PDF, JPG, PNG · Max 5 MB</p>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Step 3: Review */}
          {step === 3 && (
            <div className="space-y-4 text-sm">
              <ReviewRow label="Full Name" value={form.full_name} />
              <ReviewRow label="Email" value={form.email} />
              <ReviewRow label="Phone" value={form.phone} />
              <ReviewRow label="Business Name" value={form.business_name} />
              <ReviewRow label="Business Type" value={form.business_type} />
              <ReviewRow label="Monthly Volume" value={form.expected_monthly_volume ? `$${form.expected_monthly_volume}` : ''} />
              <div className="border-t pt-3">
                <p className="font-medium text-gray-700 mb-2">Documents</p>
                {['pan', 'aadhaar', 'bank_statement'].map(k => (
                  <div key={k} className="flex justify-between py-1">
                    <span className="text-gray-500 capitalize">{k.replace('_', ' ')}</span>
                    <span className={uploadedDocs[k] ? 'text-green-600' : 'text-red-500'}>
                      {uploadedDocs[k] ? '✓ ' + uploadedDocs[k].original_filename : '✗ Not uploaded'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Navigation */}
        <div className="flex justify-between mt-6">
          <button onClick={() => setStep(s => Math.max(0, s - 1))} disabled={step === 0}
            className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-40 transition">
            ← Previous
          </button>
          <div className="flex gap-3">
            {editable && step < 3 && (
              <button onClick={saveProgress} disabled={saving}
                className="px-4 py-2 text-sm border border-blue-300 text-blue-600 rounded-lg hover:bg-blue-50 transition disabled:opacity-60">
                {saving ? 'Saving...' : 'Save Progress'}
              </button>
            )}
            {step < 3 ? (
              <button onClick={() => { saveProgress(); setStep(s => s + 1) }}
                className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition">
                Next →
              </button>
            ) : editable ? (
              <button onClick={handleSubmit} disabled={submitting}
                className="px-6 py-2 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 transition disabled:opacity-60 font-semibold">
                {submitting ? 'Submitting...' : 'Submit KYC'}
              </button>
            ) : (
              <span className="text-sm text-gray-400 italic">Submission is {submission.state}</span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function Field({ label, value, onChange, type = 'text', disabled, placeholder }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      <input type={type} value={value} disabled={disabled} placeholder={placeholder}
        onChange={e => onChange(e.target.value)}
        className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-500" />
    </div>
  )
}

function ReviewRow({ label, value }) {
  return (
    <div className="flex justify-between py-1.5 border-b border-gray-100">
      <span className="text-gray-500">{label}</span>
      <span className="font-medium text-gray-800">{value || <span className="text-gray-300">—</span>}</span>
    </div>
  )
}
