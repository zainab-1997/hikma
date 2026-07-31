import GeneratedOrderReview from '../GeneratedOrderReview'
import ProductMatchCard from '../ProductMatchCard'

const CUSTOMER_TYPES = ['pharmacy', 'hospital', 'drug_store', 'office', 'unknown']

function label(value) {
  if (!value) return 'Unknown'
  return value.split('_').map((word) => word.charAt(0).toUpperCase() + word.slice(1)).join(' ')
}

function priceLabel(value) {
  if (value === 'pharmacy') return 'Pharmacy Price'
  if (value === 'drug_store') return 'Drug Store Price'
  return 'Unknown'
}

function Stepper({ generated }) {
  const current = generated ? 3 : 2
  return (
    <ol className="mobile-order-stepper" aria-label="Order progress">
      {['Parse', 'Review', 'Generate'].map((name, index) => {
        const step = index + 1
        return (
          <li key={name} className={step <= current ? 'is-active' : ''} aria-current={step === current ? 'step' : undefined}>
            <span>Step {step}</span>
            <strong>{name}</strong>
          </li>
        )
      })}
    </ol>
  )
}

function NoticeGroup({ title, items, tone = 'info' }) {
  if (!items?.length) return null
  return (
    <div className={`mobile-notice mobile-notice--${tone}`}>
      <strong>{title}</strong>
      <ul>{items.map((item, index) => <li key={`${item.message || item}-${index}`}>{item.message || item}</li>)}</ul>
    </div>
  )
}

function MobileOrderReview({
  editableOrder, reviewResult, matchResult, priceTypeOverride, approvedSelections,
  approvingIndex, approvalErrors, onCustomerFieldChange, onTransitFieldChange,
  onProductFieldChange, onPriceTypeOverrideChange, onApproveSelection, onReapply,
  isReapplying, onConfirm, canConfirm, isGenerating, generatedOrder, onNewOrder,
}) {
  if (!editableOrder || !reviewResult || !matchResult) return null

  const blockingErrors = reviewResult.blocking_errors || []
  const informationalNotices = reviewResult.informational_notices || []
  const confirmations = reviewResult.required_confirmations || []
  const missing = reviewResult.missing_information || []
  const warnings = reviewResult.warnings || []
  const notes = reviewResult.order_notes || []
  const hasNotices = blockingErrors.length || informationalNotices.length || confirmations.length
    || missing.length || warnings.length || notes.length
  const isTransit = editableOrder.transit.is_transit
  const unresolved = matchResult.products.filter(
    (product, index) => product.match_status !== 'matched' && !approvedSelections[index],
  ).length

  return (
    <div className="mobile-order-review">
      <Stepper generated={Boolean(generatedOrder)} />

      {!generatedOrder && (
        <>
          <section className="mobile-review-section">
            <header><span>Customer</span><strong dir="auto">{reviewResult.order_title}</strong></header>
            <div className="mobile-review-fields">
              <label className="field"><span className="field__label">Customer Name</span>
                <input className="field__input" dir="auto"
                  value={(isTransit ? reviewResult.customer.customer_name : editableOrder.customer.customer_name) || ''}
                  disabled={isTransit}
                  onChange={(event) => onCustomerFieldChange('customer_name', event.target.value)} />
              </label>
              <label className="field"><span className="field__label">Customer Type</span>
                <select className="field__input"
                  value={isTransit ? reviewResult.customer.customer_type : editableOrder.customer.customer_type}
                  disabled={isTransit}
                  onChange={(event) => onCustomerFieldChange('customer_type', event.target.value)}>
                  {CUSTOMER_TYPES.map((type) => <option key={type} value={type}>{label(type)}</option>)}
                </select>
              </label>
              <label className="field"><span className="field__label">Governorate</span>
                <input className="field__input" dir="auto" placeholder="Optional"
                  value={editableOrder.customer.governorate || ''}
                  onChange={(event) => onCustomerFieldChange('governorate', event.target.value)} />
              </label>
              <label className="field"><span className="field__label">City</span>
                <input className="field__input" dir="auto" placeholder="Optional"
                  value={editableOrder.customer.city || ''}
                  onChange={(event) => onCustomerFieldChange('city', event.target.value)} />
              </label>
              <label className="field"><span className="field__label">Area</span>
                <input className="field__input" dir="auto" placeholder="Optional"
                  value={editableOrder.customer.area || ''}
                  onChange={(event) => onCustomerFieldChange('area', event.target.value)} />
              </label>
            </div>
            <div className="mobile-price-row">
              <span>Selected Price Type</span><strong>{priceLabel(reviewResult.price_type)}</strong>
            </div>
            {isTransit && (
              <div className="mobile-review-fields">
                <label className="field"><span className="field__label">Transit From</span>
                  <input className="field__input" dir="auto" value={editableOrder.transit.primary_customer || ''}
                    onChange={(event) => onTransitFieldChange('primary_customer', event.target.value)} />
                </label>
                <label className="field"><span className="field__label">Transit To</span>
                  <input className="field__input" dir="auto" value={editableOrder.transit.destination_customer || ''}
                    onChange={(event) => onTransitFieldChange('destination_customer', event.target.value)} />
                </label>
              </div>
            )}
            {reviewResult.price_type_requires_confirmation && (
              <fieldset className="mobile-price-choice">
                <legend>Confirm price type</legend>
                <label><input type="radio" name="mobile-price-type" checked={priceTypeOverride === 'pharmacy'}
                  onChange={() => onPriceTypeOverrideChange('pharmacy')} /> Pharmacy Price</label>
                <label><input type="radio" name="mobile-price-type" checked={priceTypeOverride === 'drug_store'}
                  onChange={() => onPriceTypeOverrideChange('drug_store')} /> Drug Store Price</label>
              </fieldset>
            )}
            <button type="button" className="btn btn--secondary mobile-review-section__apply"
              onClick={onReapply} disabled={isReapplying}>
              {isReapplying ? 'Updating…' : 'Apply Changes'}
            </button>
          </section>

          <section className="mobile-review-section">
            <header><span>Products</span><strong>{matchResult.products.length}</strong></header>
            <div className="product-match-list">
              {matchResult.products.map((product, index) => (
                <ProductMatchCard
                  key={`${product.written_product_name}-${index}`}
                  product={product}
                  approvedSelection={approvedSelections[index]}
                  warnings={[...blockingErrors, ...warnings].filter(
                    (warning) => warning.details?.product_name === product.written_product_name,
                  )}
                  onQuantityChange={(value) => onProductFieldChange(index, 'quantity', value)}
                  onFreeQuantityChange={(value) => onProductFieldChange(index, 'free_quantity', value)}
                  onApprove={(candidate) => onApproveSelection(index, candidate)}
                  isApproving={approvingIndex === index}
                  approvalError={approvalErrors[index]}
                />
              ))}
            </div>
          </section>

          {hasNotices && (
            <section className="mobile-review-section">
              <header><span>Warnings</span></header>
              <NoticeGroup title="Blocking errors" items={blockingErrors} tone="danger" />
              <NoticeGroup title="Required confirmations" items={confirmations} tone="danger" />
              <NoticeGroup title="Missing required information" items={missing} tone="danger" />
              <NoticeGroup title="Warnings" items={warnings} tone="warning" />
              <NoticeGroup title="Optional information not provided" items={informationalNotices} />
              <NoticeGroup title="Order notes" items={notes} />
            </section>
          )}

          <section className={`mobile-generate-action ${canConfirm ? 'is-ready' : ''}`}>
            <div><strong>Generate Excel</strong>
              <span>{canConfirm ? 'Order is ready' : `${blockingErrors.length + confirmations.length + missing.length + unresolved} items need attention`}</span>
            </div>
            <button type="button" className="btn btn--primary" onClick={onConfirm}
              disabled={!canConfirm || isGenerating}>
              {isGenerating ? 'Generating…' : 'Generate Excel'}
            </button>
          </section>
        </>
      )}

      {generatedOrder && (
        <GeneratedOrderReview generatedOrder={generatedOrder}
          reviewResult={reviewResult} matchResult={matchResult}
          approvedSelections={approvedSelections} onNewOrder={onNewOrder} />
      )}
    </div>
  )
}

export default MobileOrderReview
