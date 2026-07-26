import { forwardRef, useState } from 'react'
import AppIcon from './ui/AppIcon'

const PLACEHOLDER = `صيدلية العين
فانكو ٥٠٠ × 20
اتكيور × 10
ميدازولام × 5`

const OrderInput = forwardRef(function OrderInput(
  { value, onChange, onAnalyze, onClear, isLoading, processingStage },
  ref,
) {
  const [exampleOpen, setExampleOpen] = useState(false)

  const handleChange = (event) => {
    onChange(event.target.value)
  }

  const useExample = () => {
    if (value && !window.confirm('Replace the current message with the example order?')) return
    onChange(PLACEHOLDER)
  }

  return (
    <section className="card order-input" aria-labelledby="order-input-title">
      <div className="order-card-heading">
        <span className="order-card-heading__icon"><AppIcon name="message" /></span>
        <div><h2 id="order-input-title">Paste WhatsApp Order</h2>
          <p>Paste the customer’s message exactly as received. We’ll identify the customer, products, quantities, and order type.</p></div>
      </div>
      <label htmlFor="order-message" className="order-input__label">Customer message</label>
      <textarea
        id="order-message"
        ref={ref}
        className="order-input__textarea"
        dir="auto"
        rows={8}
        placeholder={PLACEHOLDER}
        value={value}
        onChange={handleChange}
        disabled={isLoading}
      />
      <div className="order-input__meta"><span>{value.length.toLocaleString()} characters</span><span>Arabic and English supported</span></div>
      <div className="order-input__example">
        <button type="button" className="order-input__example-toggle" aria-expanded={exampleOpen}
          onClick={() => setExampleOpen((open) => !open)}>
          {exampleOpen ? 'Hide example' : 'View example format'}
        </button>
        {exampleOpen && <div className="order-input__example-body">
          <pre dir="rtl">{PLACEHOLDER}</pre>
          <button type="button" className="btn btn--ghost btn--small" onClick={useExample}>Use this example</button>
        </div>}
      </div>
      {isLoading && <div className="order-processing-inline" role="status" aria-live="polite">
        <span className="order-processing-inline__spinner" />
        <div><strong>{processingStage || 'Analyzing order…'}</strong><span>Your original message is preserved while we process it.</span></div>
      </div>}
      <div className="order-input__actions">
        <button type="button" className="btn btn--secondary" onClick={onClear} disabled={!value || isLoading}>Clear</button>
        <button type="button" className="btn btn--primary" onClick={onAnalyze} disabled={!value.trim() || isLoading}>
          {isLoading ? 'Analyzing order…' : 'Analyze Order'}
        </button>
      </div>
    </section>
  )
})

export default OrderInput
