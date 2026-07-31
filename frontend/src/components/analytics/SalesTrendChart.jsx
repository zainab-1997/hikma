const number = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })

function SalesTrendChart({ rows, granularity, onGranularityChange }) {
  const max = Math.max(...rows.map((row) => row.sales_total), 0)
  const points = rows.map((row, index) => {
    const x = rows.length === 1 ? 50 : 5 + (index / (rows.length - 1)) * 90
    const y = max ? 92 - (row.sales_total / max) * 82 : 92
    return `${x},${y}`
  }).join(' ')
  return (
    <>
      <div className="analytics-toolbar">
        <div className="chart-legend"><span aria-hidden="true" /> Sales total</div>
        <div className="granularity-control" aria-label="Sales trend granularity">
          {['daily', 'weekly', 'monthly'].map((value) => <button type="button" key={value}
            className={granularity === value ? 'granularity-control__active' : ''}
            aria-pressed={granularity === value} onClick={() => onGranularityChange(value)}>
            {value.charAt(0).toUpperCase() + value.slice(1)}
          </button>)}
        </div>
      </div>
      {!rows.length ? <div className="analytics-empty">No sales data for these filters.</div> : (
        <>
          <div className="trend-chart" aria-hidden="true">
            <svg viewBox="0 0 100 100" preserveAspectRatio="none">
              <line x1="5" y1="92" x2="95" y2="92" className="trend-chart__axis" />
              <polyline points={points} className="trend-chart__line" />
              {points.split(' ').map((point, index) => {
                const [cx, cy] = point.split(',')
                return <circle key={rows[index].period} cx={cx} cy={cy} r="1.5" className="trend-chart__point">
                  <title>{rows[index].period}: {number.format(rows[index].sales_total)} IQD</title>
                </circle>
              })}
            </svg>
          </div>
          <div className="analytics-table-wrap">
            <table className="analytics-table mobile-card-table">
              <thead><tr><th scope="col">Period</th><th scope="col">Sales</th><th scope="col">Orders</th><th scope="col">Quantity</th><th scope="col">Free</th></tr></thead>
              <tbody>{rows.map((row) => <tr key={row.period}>
                <td data-label="Period">{row.period}</td><td data-label="Sales">{number.format(row.sales_total)} IQD</td><td data-label="Orders">{number.format(row.order_count)}</td>
                <td data-label="Quantity">{number.format(row.ordered_quantity)}</td><td data-label="Free">{number.format(row.free_quantity)}</td>
              </tr>)}</tbody>
            </table>
          </div>
        </>
      )}
    </>
  )
}

export default SalesTrendChart
