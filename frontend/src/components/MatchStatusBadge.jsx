const STATUS_LABELS = {
  matched: 'Matched',
  fuzzy: 'Needs Review',
  ambiguous: 'Ambiguous',
  strength_conflict: 'Strength Conflict',
  unmatched: 'Needs Review',
  approved: 'Confirmed',
}

function MatchStatusBadge({ status }) {
  const label = STATUS_LABELS[status] || 'Needs Review'

  return <span className={`match-status-badge match-status-badge--${status}`}>{label}</span>
}

export default MatchStatusBadge
