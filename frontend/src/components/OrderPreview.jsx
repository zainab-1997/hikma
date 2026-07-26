import EmailOrderPanel from './EmailOrderPanel'
import ProductMatchCard from './ProductMatchCard'
import AppIcon from './ui/AppIcon'
import { resolveApiUrl } from '../services/api'

const CUSTOMER_TYPE_OPTIONS = ['pharmacy', 'hospital', 'drug_store', 'office', 'unknown']

function formatLabel(value) {
  if (!value) return 'Unknown'
  return value.split('_').map((word) => word.charAt(0).toUpperCase() + word.slice(1)).join(' ')
}

function formatPriceType(priceType) {
  if (priceType === 'pharmacy') return 'Pharmacy Price'
  if (priceType === 'drug_store') return 'Drug Store Price'
  return 'Unknown'
}

function ReviewCallout({ tone, title, items }) {
  if (!items.length) return null
  return (
    <section className={`review-callout review-callout--${tone}`}>
      <div className="review-callout__title"><span aria-hidden="true">{tone === 'danger' ? '!' : 'i'}</span><h3>{title}</h3></div>
      <ul>{items.map((item, index) => <li key={index}>{item.message || item}</li>)}</ul>
    </section>
  )
}

function OrderPreview({
  editableOrder, reviewResult, matchResult, priceTypeOverride, approvedSelections,
  approvingIndex, approvalErrors, onCustomerFieldChange, onTransitFieldChange,
  onProductFieldChange, onPriceTypeOverrideChange, onApproveSelection, onReapply,
  isReapplying, onEdit, onConfirm, canConfirm, isGenerating, generatedOrder, onNewOrder,
}) {
  if (!editableOrder || !reviewResult || !matchResult) return null
  const isTransit = editableOrder.transit.is_transit
  const unresolvedProducts = matchResult.products.filter(
    (product, index) => product.match_status !== 'matched' && !approvedSelections[index],
  ).length
  const blockingErrors = reviewResult.blocking_errors || []
  const informationalNotices = reviewResult.informational_notices || []
  const blockingReason = blockingErrors.length
    ? `Resolve ${blockingErrors.length} blocking ${blockingErrors.length === 1 ? 'error' : 'errors'} before generating.`
    : reviewResult.required_confirmations.length
    ? `Complete ${reviewResult.required_confirmations.length} required confirmation${reviewResult.required_confirmations.length === 1 ? '' : 's'} before generating.`
    : reviewResult.missing_information.length
      ? `Add ${reviewResult.missing_information.length} missing detail${reviewResult.missing_information.length === 1 ? '' : 's'} before generating.`
      : unresolvedProducts
        ? `Resolve ${unresolvedProducts} product ${unresolvedProducts === 1 ? 'issue' : 'issues'} before generating.`
        : !canConfirm
          ? 'Resolve the blocking warnings before generating.'
          : 'All required reviews are complete.'

  return (
    <div className="order-review-flow">
      <section className="card order-details-review" aria-labelledby="order-details-title">
        <div className="order-section-heading">
          <div><span className="order-section-heading__step">Step 2</span><h2 id="order-details-title">Customer & Order Details</h2>
            <p>Confirm the extracted information before generating the final order.</p></div>
          <span className="confidence-badge">Parse confidence {Math.round(reviewResult.confidence_score * 100)}%</span>
        </div>
        <div className="order-title-banner"><span>Order title</span><strong dir="auto">{reviewResult.order_title}</strong></div>

        <div className="order-detail-group">
          <h3>Customer</h3>
          <div className="review-grid">
            <label className="field"><span className="field__label">Customer Name</span>
              <input type="text" className="field__input" dir="auto"
                value={(isTransit ? reviewResult.customer.customer_name : editableOrder.customer.customer_name) || ''}
                disabled={isTransit} onChange={(event) => onCustomerFieldChange('customer_name', event.target.value)} />
            </label>
            <label className="field"><span className="field__label">Customer Type</span>
              <select className="field__input" value={isTransit ? reviewResult.customer.customer_type : editableOrder.customer.customer_type}
                disabled={isTransit} onChange={(event) => onCustomerFieldChange('customer_type', event.target.value)}>
                {CUSTOMER_TYPE_OPTIONS.map((option) => <option key={option} value={option}>{formatLabel(option)}</option>)}
              </select>
            </label>
            <label className="field"><span className="field__label">Governorate</span>
              <input type="text" className="field__input" dir="auto" placeholder="Not specified"
                value={editableOrder.customer.governorate || ''} onChange={(event) => onCustomerFieldChange('governorate', event.target.value)} />
            </label>
            <label className="field"><span className="field__label">Area</span>
              <input type="text" className="field__input" dir="auto" placeholder="Not specified"
                value={editableOrder.customer.area || ''} onChange={(event) => onCustomerFieldChange('area', event.target.value)} />
            </label>
          </div>
        </div>

        <div className="order-detail-grid">
          <div className="order-detail-group">
            <h3>Pricing</h3>
            <div className="order-fact"><span>Selected price type</span><strong>{formatPriceType(reviewResult.price_type)}</strong></div>
            {reviewResult.price_type_requires_confirmation && <div className="price-type-selector">
              <p className="price-type-selector__prompt"><strong>Office confirmation required.</strong> Select a price type, then reapply the rules.</p>
              <label className="price-type-selector__option"><input type="radio" name="price-type-override"
                checked={priceTypeOverride === 'pharmacy'} onChange={() => onPriceTypeOverrideChange('pharmacy')} /> Pharmacy Price</label>
              <label className="price-type-selector__option"><input type="radio" name="price-type-override"
                checked={priceTypeOverride === 'drug_store'} onChange={() => onPriceTypeOverrideChange('drug_store')} /> Drug Store Price</label>
            </div>}
          </div>
          <div className="order-detail-group">
            <h3>Transit</h3>
            <div className="order-fact"><span>Order route</span><strong>{isTransit ? 'Transit order' : 'Standard order'}</strong></div>
            {isTransit && <div className="review-grid review-grid--compact">
              <label className="field"><span className="field__label">Transit From</span>
                <input type="text" className="field__input" dir="auto" value={editableOrder.transit.primary_customer || ''}
                  onChange={(event) => onTransitFieldChange('primary_customer', event.target.value)} /></label>
              <label className="field"><span className="field__label">Transit To</span>
                <input type="text" className="field__input" dir="auto" value={editableOrder.transit.destination_customer || ''}
                  onChange={(event) => onTransitFieldChange('destination_customer', event.target.value)} /></label>
              <div className="field"><span className="field__label">Destination Type</span>
                <p className="field__readonly">{formatLabel(reviewResult.transit.destination_type)}</p></div>
            </div>}
          </div>
        </div>
        <div className="order-details-review__actions">
          <button type="button" className="btn btn--ghost" onClick={onEdit}>Return to message</button>
          <button type="button" className="btn btn--secondary" onClick={onReapply} disabled={isReapplying}>
            {isReapplying ? 'Reapplying rules…' : 'Reapply Business Rules'}
          </button>
        </div>
      </section>

      <section className="card product-review-section" aria-labelledby="product-review-title">
        <div className="order-section-heading">
          <div><span className="order-section-heading__step">Step 3</span><h2 id="product-review-title">Product Matching Review</h2>
            <p>Check entered quantities and approve any product that could not be safely matched automatically.</p></div>
          <span className={`review-count-badge ${unresolvedProducts ? 'review-count-badge--attention' : ''}`}>
            {unresolvedProducts ? `${unresolvedProducts} need review` : 'All matched'}
          </span>
        </div>
        <div className="product-review-columns" aria-hidden="true">
          <span>Entered product</span><span>Official product & quantities</span><span>Status</span>
        </div>
        <div className="product-match-list">
          {matchResult.products.map((product, index) => <ProductMatchCard
            key={`${product.written_product_name}-${index}`} product={product}
            approvedSelection={approvedSelections[index]}
            warnings={[...blockingErrors, ...reviewResult.warnings].filter(
              (warning) => warning.details?.product_name === product.written_product_name,
            )}
            onQuantityChange={(value) => onProductFieldChange(index, 'quantity', value)}
            onFreeQuantityChange={(value) => onProductFieldChange(index, 'free_quantity', value)}
            onApprove={(candidate) => onApproveSelection(index, candidate)}
            isApproving={approvingIndex === index} approvalError={approvalErrors[index]} />)}
        </div>
      </section>

      {(reviewResult.order_notes.length > 0 || reviewResult.missing_information.length > 0 ||
        blockingErrors.length > 0 || informationalNotices.length > 0 ||
        reviewResult.warnings.length > 0 || reviewResult.required_confirmations.length > 0) && (
        <section className="card order-attention-section" aria-labelledby="attention-title">
          <div className="order-section-heading"><div><span className="order-section-heading__step">Review</span>
            <h2 id="attention-title">Warnings & Confirmations</h2><p>Review every item below. Required confirmations are never completed automatically.</p></div></div>
          <div className="review-callout-grid">
            <ReviewCallout tone="danger" title="Blocking errors" items={blockingErrors} />
            <ReviewCallout tone="info" title="Order notes" items={reviewResult.order_notes} />
            <ReviewCallout tone="warning" title="Non-blocking warnings" items={reviewResult.warnings} />
            <ReviewCallout tone="info" title="Optional information not provided" items={informationalNotices} />
            <ReviewCallout tone="danger" title="Required confirmations" items={reviewResult.required_confirmations} />
          </div>
        </section>
      )}

      <section className={`card generate-order-panel ${canConfirm ? 'generate-order-panel--ready' : ''}`}>
        <div className="generate-order-panel__copy">
          <span className="order-section-heading__step">Step 4</span>
          <h2>Generate the approved Excel order</h2>
          <p>{blockingReason}</p>
        </div>
        <button type="button" className="btn btn--primary btn--large" onClick={onConfirm} disabled={!canConfirm || isGenerating}>
          {isGenerating ? 'Generating Excel order…' : 'Generate Approved Excel Order'}
        </button>
      </section>

      {generatedOrder && <>
        <section className="generated-order-success" aria-live="polite">
          <div className="generated-order-success__icon"><AppIcon name="success" size={30} /></div>
          <div className="generated-order-success__body">
            <span className="generated-order__saved">Generated and saved</span>
            <h2>Order generated successfully</h2>
            <p>The approved company workbook is ready to download or send by email.</p>
            <dl className="generated-order__details">
              <div className="generated-order__row"><dt>Order Number</dt><dd>{generatedOrder.order_number}</dd></div>
              <div className="generated-order__row"><dt>Filename</dt><dd dir="auto">{generatedOrder.filename}</dd></div>
              <div className="generated-order__row"><dt>Selected Price Type</dt><dd>{formatPriceType(generatedOrder.selected_price_type)}</dd></div>
              <div className="generated-order__row"><dt>Order Total</dt><dd>{generatedOrder.selected_order_total.toLocaleString()} IQD</dd></div>
            </dl>
            {generatedOrder.excluded_order_notes && <p className="generated-order__note">
              Order notes were not written to the workbook because the template has no designated note cell.
            </p>}
            <div className="generated-order-success__actions">
              <a className="btn btn--primary" href={resolveApiUrl(generatedOrder.download_url)} download={generatedOrder.filename}>
                <AppIcon name="download" size={17} /> Download Excel
              </a>
              <button type="button" className="btn btn--secondary" onClick={onNewOrder}>Process New Order</button>
            </div>
          </div>
        </section>
        <EmailOrderPanel orderId={generatedOrder.order_id} orderNumber={generatedOrder.order_number}
          generatedFilename={generatedOrder.filename} />
      </>}
    </div>
  )
}

export default OrderPreview
