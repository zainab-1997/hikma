import { useEffect, useState } from 'react'
import { getEmailConfig, sendOrderEmail } from '../services/api'

function parseAddressList(raw) {
  return raw
    .split(',')
    .map((address) => address.trim())
    .filter(Boolean)
}

function EmailOrderPanel({ orderId, orderNumber, generatedFilename, initiallyExpanded = false }) {
  const [config, setConfig] = useState(null)
  const [configError, setConfigError] = useState('')
  const [toInput, setToInput] = useState('')
  const [ccInput, setCcInput] = useState('')
  const [subject, setSubject] = useState('')
  const [message, setMessage] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [result, setResult] = useState(null)
  const [sendError, setSendError] = useState('')
  const [expanded, setExpanded] = useState(initiallyExpanded)

  useEffect(() => {
    getEmailConfig()
      .then((loadedConfig) => {
        setConfig(loadedConfig)
        if (loadedConfig.default_recipients.length > 0) {
          setToInput(loadedConfig.default_recipients.join(', '))
        }
      })
      .catch((err) => setConfigError(err.message || 'Failed to load email configuration.'))
  }, [])

  const toAddresses = parseAddressList(toInput)
  const ccAddresses = parseAddressList(ccInput)
  const allRecipients = [...toAddresses, ...ccAddresses]

  const handleSend = async () => {
    setSendError('')
    setResult(null)
    setIsSending(true)

    try {
      const response = await sendOrderEmail(orderId, {
        email_request_id: crypto.randomUUID(),
        to_addresses: toAddresses,
        cc_addresses: ccAddresses,
        subject_override: subject.trim() || null,
        message: message.trim() || null,
      })
      setResult(response)
      if (!response.success) {
        setSendError(response.error_message || 'The email could not be sent.')
      }
    } catch (err) {
      setSendError(err.message || 'Failed to send the order email.')
    } finally {
      setIsSending(false)
    }
  }

  if (configError) {
    return (
      <section className="card email-order email-order--unavailable">
        <div className="email-order__heading"><div><span>Email delivery</span><h3>Send generated order by email</h3></div></div>
        <p className="product-search__error">{configError}</p>
      </section>
    )
  }

  if (!config) {
    return null
  }

  if (!config.email_enabled) {
    return (
      <section className="card email-order email-order--disabled">
        <div className="email-order__heading"><div><span>Email delivery</span><h3>Send generated order by email</h3></div></div>
        <p>Email delivery is currently disabled. Downloaded orders can still be shared through your approved process.</p>
      </section>
    )
  }

  return (
    <section className="card email-order">
      <div className="email-order__heading">
        <div><span>Email delivery</span><h3>Send generated order by email</h3>
          <p>Review recipients and message details before sending.</p></div>
        <button type="button" className="btn btn--secondary btn--small" aria-expanded={expanded}
          onClick={() => setExpanded((current) => !current)}>{expanded ? 'Collapse' : 'Prepare Email'}</button>
      </div>

      {expanded && <div className="email-order__form">
      <div className="review-grid">
        <div className="field">
          <span className="field__label">Order Number</span>
          <p className="field__readonly">{orderNumber}</p>
        </div>
        <div className="field">
          <span className="field__label">Generated Filename</span>
          <p className="field__readonly">{generatedFilename}</p>
        </div>
      </div>

      <label className="field">
        <span className="field__label">To</span>
        <input
          type="text"
          className="field__input"
          value={toInput}
          onChange={(event) => setToInput(event.target.value)}
          placeholder="recipient@example.com, another@example.com"
        />
      </label>

      <label className="field">
        <span className="field__label">CC</span>
        <input
          type="text"
          className="field__input"
          value={ccInput}
          onChange={(event) => setCcInput(event.target.value)}
          placeholder="optional"
        />
      </label>

      <label className="field">
        <span className="field__label">Subject</span>
        <input
          type="text"
          className="field__input"
          value={subject}
          onChange={(event) => setSubject(event.target.value)}
          placeholder={`Hikma Order ${orderNumber} - ...`}
        />
      </label>

      <label className="field">
        <span className="field__label">Optional Message</span>
        <textarea
          className="order-input__textarea email-order__message"
          rows={3}
          value={message}
          onChange={(event) => setMessage(event.target.value)}
        />
      </label>

      {allRecipients.length > 0 && (
        <p className="email-order__preview">
          This order will be sent to: <strong>{allRecipients.join(', ')}</strong>
        </p>
      )}

      {sendError && <p className="product-search__error">{sendError}</p>}

      <button
        type="button"
        className="btn btn--primary"
        onClick={handleSend}
        disabled={isSending || allRecipients.length === 0}
      >
        {isSending ? 'Sending...' : 'Send Email'}
      </button>

      {result && result.success && (
        <div className="email-order__result" role="status" aria-live="polite">
          <p className="generated-order__saved">Sent successfully</p>
          <p>
            To: {result.to_addresses.join(', ')}
            {result.cc_addresses.length > 0 ? ` · CC: ${result.cc_addresses.join(', ')}` : ''}
          </p>
          <p>Subject: {result.subject}</p>
          <p>Sent at: {new Date(result.sent_at).toLocaleString()}</p>
        </div>
      )}
      </div>}
    </section>
  )
}

export default EmailOrderPanel
