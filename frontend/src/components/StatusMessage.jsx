function StatusMessage({ type = 'info', message, onRetry }) {
  if (!message) return null

  return (
    <div className={`status-message status-message--${type}`} role={type === 'error' ? 'alert' : 'status'}>
      <div><strong>{type === 'error' ? 'We couldn’t analyze this order.' : 'Order update'}</strong><p>{message}</p></div>
      {type === 'error' && onRetry && <button type="button" className="btn btn--secondary btn--small" onClick={onRetry}>Try again</button>}
    </div>
  )
}

export default StatusMessage
