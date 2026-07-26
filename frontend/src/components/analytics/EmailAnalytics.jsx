const metrics = [
  ['sent', 'Sent'], ['failed', 'Failed'], ['pending', 'Pending'], ['sending', 'Sending'],
  ['total_attempts', 'Total Attempts'],
]

function EmailAnalytics({ data }) {
  return <div>
    <div className="email-metrics">
      {metrics.map(([key, label]) => <div key={key} className={`email-metric email-metric--${key}`}><span>{label}</span><strong>{Number(data?.[key]) || 0}</strong></div>)}
      <div className="email-metric email-metric--rate"><span>Success Rate</span><strong>{Number(data?.success_rate) || 0}%</strong></div>
    </div>
    <p className="email-latest"><strong>Latest failure:</strong>{' '}
      {data?.latest_failure_time ? new Date(data.latest_failure_time).toLocaleString() : 'No failures recorded'}
    </p>
  </div>
}

export default EmailAnalytics
