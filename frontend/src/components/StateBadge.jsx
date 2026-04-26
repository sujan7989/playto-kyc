const colors = {
  draft: 'bg-gray-100 text-gray-700',
  submitted: 'bg-blue-100 text-blue-700',
  under_review: 'bg-yellow-100 text-yellow-700',
  approved: 'bg-green-100 text-green-700',
  rejected: 'bg-red-100 text-red-700',
  more_info_requested: 'bg-purple-100 text-purple-700',
}

const labels = {
  draft: 'Draft',
  submitted: 'Submitted',
  under_review: 'Under Review',
  approved: 'Approved',
  rejected: 'Rejected',
  more_info_requested: 'More Info Needed',
}

export default function StateBadge({ state }) {
  return (
    <span className={`inline-block text-xs font-semibold px-2.5 py-1 rounded-full ${colors[state] || 'bg-gray-100 text-gray-600'}`}>
      {labels[state] || state}
    </span>
  )
}
