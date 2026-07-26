const number = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })
const fields = [
  ['customer_name', 'Customer'], ['customer_type', 'Customer Type'], ['governorate', 'Governorate'],
  ['order_count', 'Order Count'], ['total_sales', 'Total Sales'], ['average_order_value', 'Average Order Value'],
  ['latest_order_date', 'Latest Order Date'],
]
const sortable = new Set(['customer_name', 'order_count', 'total_sales', 'average_order_value', 'latest_order_date'])

function CustomerAnalyticsTable({ data, sorting, onSort, onPage }) {
  const { items = [], total = 0, limit = 10, offset = 0 } = data || {}
  const display = (item, field) => {
    if (field === 'total_sales' || field === 'average_order_value') return `${number.format(item[field] || 0)} IQD`
    if (field === 'latest_order_date') return item[field] ? new Date(item[field]).toLocaleString() : '—'
    return item[field] || 'Unknown'
  }
  return <>
    {!items.length ? <div className="analytics-empty">No customers for these filters.</div> : (
      <div className="analytics-table-wrap"><table className="analytics-table">
        <thead><tr>{fields.map(([field, label]) => <th key={field} scope="col">
          {sortable.has(field) ? <button type="button" className="table-sort" onClick={() => onSort(field)}>
            {label}{sorting.sort_by === field ? (sorting.sort_direction === 'asc' ? ' ↑' : ' ↓') : ''}
          </button> : label}
        </th>)}</tr></thead>
        <tbody>{items.map((item) => <tr key={`${item.customer_name}-${item.customer_type}-${item.governorate}`}>
          {fields.map(([field]) => <td key={field} dir={['customer_name', 'governorate'].includes(field) ? 'auto' : undefined}
            className={['order_count', 'total_sales', 'average_order_value'].includes(field) ? 'numeric-cell' : ''}>{display(item, field)}</td>)}
        </tr>)}</tbody>
      </table></div>
    )}
    <Pagination total={total} limit={limit} offset={offset} onPage={onPage} />
  </>
}

export function Pagination({ total, limit, offset, onPage }) {
  const start = total ? offset + 1 : 0
  const end = Math.min(offset + limit, total)
  return <div className="analytics-pagination">
    <span>{start}–{end} of {total}</span>
    <div>
      <button type="button" className="btn btn--secondary btn--compact" disabled={offset === 0} onClick={() => onPage(Math.max(0, offset - limit))}>Previous</button>
      <button type="button" className="btn btn--secondary btn--compact" disabled={offset + limit >= total} onClick={() => onPage(offset + limit)}>Next</button>
    </div>
  </div>
}

export default CustomerAnalyticsTable
