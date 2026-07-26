const STATUS_LABELS = { pending: 'Pending', sending: 'Sending', sent: 'Sent', failed: 'Failed' }

function formatDateTime(value) {
  if (!value) return 'Not recorded'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

function EmailDeliveryList({ deliveries, compact = false }) {
  if (deliveries.length === 0) {
    return <div className="email-history-empty"><strong>No email attempts yet</strong>
      <p>This order has not been sent through the application.</p></div>
  }

  return (
    <ol className={`email-timeline ${compact ? 'email-timeline--compact' : ''}`}>
      {deliveries.map((delivery) => <li key={delivery.delivery_id}
        className={`email-timeline__item email-timeline__item--${delivery.status}`}>
        <span className="email-timeline__marker" aria-hidden="true" />
        <article>
          <header><div><strong>Attempt {delivery.attempt_number}</strong><span>{formatDateTime(delivery.created_at)}</span></div>
            <span className={`email-status-badge email-status-badge--${delivery.status}`}>
              {STATUS_LABELS[delivery.status] || delivery.status}
            </span></header>
          <dl className="email-attempt-details">
            <div><dt>To</dt><dd>{delivery.to_addresses.join(', ') || 'Not provided'}</dd></div>
            {delivery.cc_addresses.length > 0 && <div><dt>CC</dt><dd>{delivery.cc_addresses.join(', ')}</dd></div>}
            <div><dt>Subject</dt><dd>{delivery.subject}</dd></div>
            {delivery.sent_at && <div><dt>Sent</dt><dd>{formatDateTime(delivery.sent_at)}</dd></div>}
          </dl>
          {delivery.safe_error_message && <p className="email-attempt-error"><strong>Delivery failed:</strong> {delivery.safe_error_message}</p>}
        </article>
      </li>)}
    </ol>
  )
}

export default EmailDeliveryList
