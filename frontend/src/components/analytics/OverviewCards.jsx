const integer = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })
const cards = [
  ['total_orders', 'Total Orders'],
  ['total_sales_value', 'Total Sales', true],
  ['total_ordered_quantity', 'Ordered Quantity'],
  ['total_free_quantity', 'Free Quantity'],
  ['average_order_value', 'Average Order Value', true],
  ['unique_customers', 'Unique Customers'],
  ['unique_governorates', 'Unique Governorates'],
  ['sent_email_count', 'Sent Emails'],
  ['failed_email_count', 'Failed Emails'],
]

function OverviewCards({ data }) {
  return (
    <div className="overview-grid">
      {cards.map(([key, label, money]) => (
        <article className="metric-card" key={key}>
          <div className="metric-card__label"><span className="metric-card__indicator" aria-hidden="true" /><span>{label}</span></div>
          <strong>{integer.format(Number(data?.[key]) || 0)}{money && <small> IQD</small>}</strong>
        </article>
      ))}
    </div>
  )
}

export default OverviewCards
