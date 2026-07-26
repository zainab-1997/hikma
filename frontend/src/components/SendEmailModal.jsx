import EmailOrderPanel from './EmailOrderPanel'
import Modal from './ui/Modal'

function SendEmailModal({ orderId, orderNumber, generatedFilename, onClose }) {
  return (
    <Modal title="Send Order Email" description={`Review recipients before sending order ${orderNumber}.`}
      onClose={onClose} size="medium"
      footer={<button type="button" className="btn btn--secondary" onClick={onClose}>Close</button>}>
      <EmailOrderPanel orderId={orderId} orderNumber={orderNumber}
        generatedFilename={generatedFilename} initiallyExpanded />
    </Modal>
  )
}

export default SendEmailModal
