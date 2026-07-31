import { forwardRef } from 'react'

const PLACEHOLDER = `صيدلية العين
فانكو ٥٠٠ × 20
اتكيور × 10`

const MobileOrderInput = forwardRef(function MobileOrderInput(
  { value, onChange, onAnalyze, isLoading, processingStage },
  ref,
) {
  return (
    <section className="mobile-order-input" aria-labelledby="mobile-order-input-title">
      <h2 id="mobile-order-input-title">Paste WhatsApp Order</h2>
      <textarea
        id="mobile-order-message"
        ref={ref}
        dir="auto"
        rows={10}
        placeholder={PLACEHOLDER}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={isLoading}
      />
      {isLoading && (
        <div className="mobile-order-input__processing" role="status" aria-live="polite">
          <span aria-hidden="true" />
          <strong>{processingStage || 'Analyzing order…'}</strong>
        </div>
      )}
      <button
        type="button"
        className="btn btn--primary mobile-order-input__analyze"
        onClick={onAnalyze}
        disabled={!value.trim() || isLoading}
      >
        {isLoading ? 'Analyzing Order…' : 'Analyze Order'}
      </button>
    </section>
  )
})

export default MobileOrderInput
