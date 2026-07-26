import { useEffect, useState } from 'react'
import { listOrderEmails } from '../services/api'
import EmailDeliveryList from './EmailDeliveryList'
import Modal from './ui/Modal'

function EmailHistoryModal({ orderId, onClose }) {
  const [deliveries, setDeliveries] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    listOrderEmails(orderId)
      .then((result) => { if (!cancelled) setDeliveries(result) })
      .catch((err) => { if (!cancelled) setError(err.message || 'Failed to load email history.') })
    return () => { cancelled = true }
  }, [orderId])

  return (
    <Modal title="Email Delivery History" description="Delivery attempts are shown newest first."
      onClose={onClose} size="medium"
      footer={<button type="button" className="btn btn--secondary" onClick={onClose}>Close</button>}>
      {error && <div className="modal-state modal-state--error" role="alert">Unable to load email delivery history.</div>}
      {deliveries === null && !error && <div className="modal-state" role="status">Loading delivery history…</div>}
      {deliveries && <EmailDeliveryList deliveries={deliveries} />}
    </Modal>
  )
}

export default EmailHistoryModal
