const number = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })
const priceLabel = (value) => value === 'pharmacy' ? 'Pharmacy & Hospitals' : value === 'drug_store' ? 'Drug Store' : value

export function GovernorateAnalytics({ rows }) {
  const max = Math.max(...rows.map((row) => row.sales_total), 0)
  if (!rows.length) return <div className="analytics-empty">No governorate data for these filters.</div>
  return <div className="rank-list">{rows.map((row) => <div className="rank-row" key={row.governorate}>
    <div className="rank-row__label"><strong>{row.governorate}</strong><span>{row.order_count} orders · {number.format(row.sales_total)} IQD · {row.percentage_of_total_sales}%</span></div>
    <div className="rank-row__track"><span style={{ width: `${max ? (row.sales_total / max) * 100 : 0}%` }} /></div>
  </div>)}</div>
}

function SplitTable({ rows, type }) {
  if (!rows.length) return <div className="analytics-empty">No breakdown data for these filters.</div>
  const nameKey = type === 'price' ? 'price_type' : 'customer_type'
  return <div className="analytics-table-wrap"><table className="analytics-table mobile-card-table">
    <thead><tr><th scope="col">{type === 'price' ? 'Price Type' : 'Customer Type'}</th><th scope="col">Orders</th><th scope="col">Sales</th>{type === 'price' && <th scope="col">Share</th>}</tr></thead>
    <tbody>{rows.map((row) => <tr key={row[nameKey]}>
      <td data-label={type === 'price' ? 'Price Type' : 'Customer Type'}>{type === 'price' ? priceLabel(row[nameKey]) : row[nameKey]}</td>
      <td data-label="Orders">{number.format(row.order_count)}</td><td data-label="Sales">{number.format(row.sales_total)} IQD</td>
      {type === 'price' && <td data-label="Share">{row.percentage_of_total_sales}%</td>}
    </tr>)}</tbody>
  </table></div>
}

export function PriceTypeSplit({ rows }) { return <SplitTable rows={rows} type="price" /> }
export function CustomerTypeSplit({ rows }) { return <SplitTable rows={rows} type="customer" /> }
