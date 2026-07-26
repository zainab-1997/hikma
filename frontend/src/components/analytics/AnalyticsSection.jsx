function AnalyticsSection({ title, subtitle, loading, error, onRetry, children, className = '' }) {
  return (
    <section className={`analytics-section card ${className}`}>
      <div className="analytics-section__header">
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
      </div>
      {loading ? (
        <div className="analytics-state" role="status">Loading this section…</div>
      ) : error ? (
        <div className="analytics-state analytics-state--error">
          <p>Unable to load this analytics section.</p>
          <button type="button" className="btn btn--secondary btn--compact" onClick={onRetry}>Retry</button>
        </div>
      ) : children}
    </section>
  )
}

export default AnalyticsSection
