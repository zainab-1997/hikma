import { Pagination } from './CustomerAnalyticsTable'

const number = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })
const fields = [
  ['official_product_name', 'Official Product Name'], ['total_quantity', 'Total Quantity'],
  ['total_free_quantity', 'Total Free Quantity'], ['order_count', 'Order Count'],
  ['unique_customer_count', 'Unique Customers'],
]

function ProductAnalyticsTable({ data, sorting, onSort, onPage }) {
  const { items = [], total = 0, limit = 10, offset = 0 } = data || {}
  return <>
    <p className="analytics-note">Historical product value is unavailable because unit price was not stored per order line.</p>
    {!items.length ? <div className="analytics-empty">No products for these filters.</div> : (
      <div className="analytics-table-wrap"><table className="analytics-table">
        <thead><tr>{fields.map(([field, label]) => <th key={field} scope="col"><button type="button" className="table-sort" onClick={() => onSort(field)}>
          {label}{sorting.sort_by === field ? (sorting.sort_direction === 'asc' ? ' ↑' : ' ↓') : ''}
        </button></th>)}</tr></thead>
        <tbody>{items.map((item) => <tr key={item.official_product_name}>
          <td dir="auto">{item.official_product_name}</td><td className="numeric-cell">{number.format(item.total_quantity)}</td>
          <td className="numeric-cell">{number.format(item.total_free_quantity)}</td><td className="numeric-cell">{number.format(item.order_count)}</td>
          <td className="numeric-cell">{number.format(item.unique_customer_count)}</td>
        </tr>)}</tbody>
      </table></div>
    )}
    <Pagination total={total} limit={limit} offset={offset} onPage={onPage} />
  </>
}

export default ProductAnalyticsTable
