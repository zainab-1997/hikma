function StatusIndicator({ status, label, action }) {
  return (
    <div className={`status-indicator status-indicator--${status}`} role="status">
      <span className="status-indicator__dot" aria-hidden="true" />
      <span className="status-indicator__label">{label}</span>
      {action}
    </div>
  )
}

export default StatusIndicator
