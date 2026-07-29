import AppIcon from '../ui/AppIcon'

function friendly(value) {
  if (!value) return 'Not available'
  return value.split('_').map((word) => word.charAt(0).toUpperCase() + word.slice(1)).join(' ')
}

function OrderSummaryCard({ reviewResult, matchResult, approvedSelections }) {
  if (!reviewResult || !matchResult) {
    return (
      <section className="order-rail-card order-rail-card--muted">
        <div className="order-rail-card__heading"><AppIcon name="info" size={17} /><h2>What happens next?</h2></div>
        <p>We’ll identify customer details, apply order rules, and compare each entered product with the official catalog.</p>
        <p>Nothing is generated until every required review is complete.</p>
      </section>
    )
  }

  const totalQuantity = matchResult.products.reduce((sum, product) => sum + (product.quantity || 0), 0)
  const totalFree = matchResult.products.reduce((sum, product) => sum + product.free_quantity, 0)
  const unresolved = matchResult.products.filter(
    (product, index) => product.match_status !== 'matched' && !approvedSelections[index],
  ).length
  const blockingErrors = reviewResult.blocking_errors?.length || 0
  const rows = [
    ['Customer', reviewResult.customer.customer_name || 'Unknown'],
    ['Products', matchResult.products.length],
    ['Ordered quantity', totalQuantity],
    ['Free quantity', totalFree],
    ['Price type', friendly(reviewResult.price_type)],
    ['Transit', reviewResult.transit.is_transit ? 'Yes' : 'No'],
    ['Product issues', unresolved],
    ['Blocking errors', blockingErrors],
    ['Confirmations', reviewResult.required_confirmations.length],
  ]

  return (
    <section className="order-rail-card" aria-labelledby="order-summary-title">
      <div className="order-rail-card__heading"><AppIcon name="summary" size={17} /><h2 id="order-summary-title">Order summary</h2></div>
      <dl className="order-summary-list">
        {rows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd dir={label === 'Customer' ? 'auto' : undefined}>{value}</dd></div>)}
      </dl>
      <div className={`order-readiness ${unresolved || blockingErrors || reviewResult.required_confirmations.length ? 'order-readiness--attention' : 'order-readiness--ready'}`}>
        <strong>{unresolved || blockingErrors || reviewResult.required_confirmations.length ? 'Attention required' : 'Review on track'}</strong>
        <span>{blockingErrors ? `${blockingErrors} blocking ${blockingErrors === 1 ? 'error' : 'errors'}.` : unresolved ? `${unresolved} product ${unresolved === 1 ? 'needs' : 'need'} review.` : 'All required items are resolved.'}</span>
      </div>
    </section>
  )
}

export default OrderSummaryCard
