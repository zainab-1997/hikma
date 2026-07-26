import { useEffect, useState } from 'react'
import { getOrderDetail, listOrderEmails, resolveApiUrl } from '../services/api'
import EmailDeliveryList from './EmailDeliveryList'
import Modal from './ui/Modal'

const friendly = (value) => value ? value.split('_').map((word) => word.charAt(0).toUpperCase() + word.slice(1)).join(' ') : 'Not provided'
const priceType = (value) => value === 'pharmacy' ? 'Pharmacy & Hospital' : value === 'drug_store' ? 'Drug Store' : 'Unknown'
const dateTime = (value) => value ? new Date(value).toLocaleString() : 'Not provided'

function DetailValue({ label, value, direction }) {
  return <div className="detail-value"><dt>{label}</dt><dd dir={direction}>{value || 'Not provided'}</dd></div>
}

function OrderDetailModal({ orderId, onClose, onSendEmail }) {
  const [detail, setDetail] = useState(null)
  const [error, setError] = useState('')
  const [emailDeliveries, setEmailDeliveries] = useState(null)
  const [emailError, setEmailError] = useState('')
  const isLoading = detail === null && !error

  useEffect(() => {
    let cancelled = false
    getOrderDetail(orderId)
      .then((result) => { if (!cancelled) setDetail(result) })
      .catch((err) => { if (!cancelled) setError(err.message || 'Failed to load order details.') })
    return () => { cancelled = true }
  }, [orderId])

  useEffect(() => {
    let cancelled = false
    listOrderEmails(orderId)
      .then((result) => { if (!cancelled) setEmailDeliveries(result) })
      .catch((err) => { if (!cancelled) setEmailError(err.message || 'Failed to load email history.') })
    return () => { cancelled = true }
  }, [orderId])

  const footer = detail ? <>
    <button type="button" className="btn btn--secondary" onClick={onClose}>Close</button>
    {onSendEmail && <button type="button" className="btn btn--secondary" onClick={onSendEmail}>Send Email</button>}
    <a className="btn btn--primary" href={resolveApiUrl(detail.download_url)} download={detail.generated_filename}>Download Excel</a>
  </> : <button type="button" className="btn btn--secondary" onClick={onClose}>Close</button>

  return (
    <Modal title={detail?.order_number || 'Order Details'}
      description={detail ? `Created ${dateTime(detail.created_at)}` : 'Loading the complete saved order record.'}
      onClose={onClose} size="large" footer={footer}>
      {isLoading && <div className="modal-state" role="status">Loading order details…</div>}
      {error && <div className="modal-state modal-state--error" role="alert">Unable to load this order record.</div>}
      {detail && <div className="order-detail-record">
        <section className="detail-section">
          <div className="detail-section__heading"><h3>Customer information</h3>
            <span className={`email-status-badge email-status-badge--${detail.email_status || 'none'}`}>
              {detail.email_status ? friendly(detail.email_status) : 'Not sent'}
            </span></div>
          <dl className="detail-value-grid">
            <DetailValue label="Customer" value={detail.customer_name} direction="auto" />
            <DetailValue label="Customer Type" value={friendly(detail.customer_type)} />
            <DetailValue label="Governorate" value={detail.governorate} direction="auto" />
            <DetailValue label="Area" value={detail.area} direction="auto" />
            <DetailValue label="Phone" value={detail.phone_number} />
            <DetailValue label="Order Title" value={detail.order_title} direction="auto" />
          </dl>
        </section>

        <section className="detail-section">
          <div className="detail-section__heading"><h3>Pricing and transit</h3></div>
          <dl className="detail-value-grid">
            <DetailValue label="Price Type" value={priceType(detail.selected_price_type)} />
            <DetailValue label="Order Total" value={`${detail.selected_order_total.toLocaleString()} IQD`} />
            <DetailValue label="Transit Status" value={detail.is_transit ? 'Transit order' : 'Standard order'} />
            {detail.is_transit && <DetailValue label="Transit From" value={detail.primary_customer} direction="auto" />}
            {detail.is_transit && <DetailValue label="Transit To" value={detail.destination_customer} direction="auto" />}
          </dl>
        </section>

        <section className="detail-section">
          <div className="detail-section__heading"><h3>Product lines</h3><span>{detail.products.length} products</span></div>
          <div className="data-table-wrap">
            <table className="data-table detail-products-table">
              <thead><tr><th scope="col">Official Product</th><th scope="col">Entered Name</th>
                <th scope="col" className="numeric-cell">Quantity</th><th scope="col" className="numeric-cell">Free</th>
                <th scope="col">Bonus</th><th scope="col">Match</th></tr></thead>
              <tbody>{detail.products.map((product, index) => <tr key={`${product.official_product_name}-${index}`}>
                <td data-label="Official Product" dir="auto"><strong>{product.official_product_name}</strong>
                  {product.product_note && <small dir="auto">{product.product_note}</small>}</td>
                <td data-label="Entered Name" dir="auto">{product.written_product_name}</td>
                <td data-label="Quantity" className="numeric-cell">{product.quantity}</td>
                <td data-label="Free" className="numeric-cell">{product.free_quantity}</td>
                <td data-label="Bonus">{product.free_percentage != null ? `${product.free_percentage}%` : '—'}</td>
                <td data-label="Match"><span className="record-badge">{friendly(product.match_status)}</span></td>
              </tr>)}</tbody>
            </table>
          </div>
        </section>

        <section className="detail-section detail-file">
          <div className="detail-section__heading"><h3>Generated file</h3></div>
          <div><span>Excel workbook</span><strong dir="auto">{detail.generated_filename || 'File unavailable'}</strong></div>
        </section>

        <section className="detail-section">
          <div className="detail-section__heading"><h3>Email delivery summary</h3></div>
          {emailError && <div className="modal-state modal-state--error">Unable to load email delivery history.</div>}
          {emailDeliveries === null && !emailError && <div className="modal-state">Loading email delivery history…</div>}
          {emailDeliveries && <EmailDeliveryList deliveries={emailDeliveries} compact />}
        </section>
      </div>}
    </Modal>
  )
}

export default OrderDetailModal
