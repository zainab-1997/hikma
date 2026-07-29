import { useState } from 'react'
import MatchStatusBadge from './MatchStatusBadge'
import ProductSearch from './ProductSearch'
import { formatQuantityInput, parseOrderQuantity } from '../utils/quantity'

function formatScore(score) {
  if (score == null) return null
  return `${Math.round(score * 100)}%`
}

function ProductMatchCard({
  product,
  approvedSelection,
  warnings,
  onQuantityChange,
  onFreeQuantityChange,
  onApprove,
  isApproving,
  approvalError,
}) {
  const [pendingCandidate, setPendingCandidate] = useState(null)
  const [showSearch, setShowSearch] = useState(false)
  const [quantityText, setQuantityText] = useState(
    formatQuantityInput(product.quantity),
  )
  const [quantityError, setQuantityError] = useState('')

  const isResolved = product.match_status === 'matched' || Boolean(approvedSelection)
  const displayOfficialName = approvedSelection?.official_name || product.matched_official_name
  const effectiveStatus = approvedSelection ? 'approved' : product.match_status

  const handleQuantityChange = (event) => {
    const rawValue = event.target.value
    setQuantityText(rawValue)
    const parsed = parseOrderQuantity(rawValue)
    setQuantityError(parsed.error)
    onQuantityChange(parsed.value)
  }

  const handleFreeQuantityChange = (event) => {
    const value = event.target.valueAsNumber
    onFreeQuantityChange(Number.isNaN(value) ? 0 : value)
  }

  const handleSelectFromSearch = (candidate) => {
    setPendingCandidate({ row: candidate.row, official_name: candidate.official_name })
    setShowSearch(false)
  }

  const handleApproveClick = () => {
    if (pendingCandidate) {
      onApprove(pendingCandidate)
    }
  }

  return (
    <article className={`product-match-card product-match-card--${effectiveStatus}`}>
      <div className="product-match-card__entered">
        <span className="product-match-card__eyebrow">Entered product</span>
        <strong className="product-match-card__name" dir="auto">{product.written_product_name}</strong>
        <span className="product-row__meta">Recognized strength: {product.strength || 'Not recognized'}</span>
        {product.concentration && <span className="product-row__meta">Concentration: {product.concentration}</span>}
        {product.dosage_form && <span className="product-row__meta">Dosage form: {product.dosage_form}</span>}
        {product.free_percentage != null && <span className="product-row__meta">Original bonus: {product.free_percentage}%</span>}
      </div>
      <div className="product-match-card__match">
        <span className="product-match-card__eyebrow">Official product</span>
        <p className="product-match-card__official-name" dir="auto">{displayOfficialName || 'Not yet selected'}</p>
        {product.match_score != null && !approvedSelection && (
          <p className="product-match-card__score">Match confidence {formatScore(product.match_score)}</p>
        )}
        <div className="product-match-card__quantities">
          <label className="field field--inline"><span className="field__label">Quantity</span>
            <input type="text" inputMode="numeric" pattern="[0-9٠-٩۰-۹]*" required
              aria-required="true" aria-invalid={Boolean(quantityError || product.quantity == null)}
              className="field__input field__input--number" value={quantityText}
              placeholder="Required / مطلوب" onChange={handleQuantityChange} />
            {(quantityError || product.quantity == null) && (
              <span className="field__error" role="alert">
                {quantityError || 'Quantity is required / الكمية مطلوبة'}
              </span>
            )}
          </label>
          <label className="field field--inline"><span className="field__label">Free</span>
            <input type="number" min="0" className="field__input field__input--number"
              value={product.free_quantity} onChange={handleFreeQuantityChange} /></label>
        </div>
      </div>
      <div className="product-match-card__status">
        <MatchStatusBadge status={effectiveStatus} />
      </div>

      {warnings.length > 0 && (
        <ul className="product-match-card__warnings">
          {warnings.map((warning, index) => (
            <li key={index}>{warning.message}</li>
          ))}
        </ul>
      )}

      {!isResolved && (
        <div className="product-match-card__resolution">
          <div className="product-match-card__resolution-heading">
            <strong>{product.match_status === 'strength_conflict' ? 'Strength confirmation required' : product.match_status === 'ambiguous' ? 'Ambiguous product match' : 'Manual product confirmation required'}</strong>
            <span>Select the correct official catalog product, then approve the match.</span>
          </div>

          {product.candidates.length > 0 && (
            <div className="candidate-list">
              <p className="candidate-list__label">Candidate matches:</p>
              {product.candidates.map((candidate) => (
                <label key={candidate.row} className="candidate-option">
                  <input
                    type="radio"
                    name={`candidate-${product.written_product_name}-${product.quantity}`}
                    checked={pendingCandidate?.row === candidate.row}
                    onChange={() => setPendingCandidate(candidate)}
                  />
                  <span dir="auto">{candidate.official_name}</span><small>{formatScore(candidate.score)} match</small>
                </label>
              ))}
            </div>
          )}

          <button type="button" className="btn btn--secondary" onClick={() => setShowSearch((prev) => !prev)}>
            {showSearch ? 'Close product search' : 'Search official catalog'}
          </button>

          {showSearch && <ProductSearch onSelect={handleSelectFromSearch} />}

          {pendingCandidate && (
            <p className="product-match-card__pending">Selected: <span dir="auto">{pendingCandidate.official_name}</span></p>
          )}

          {approvalError && <p className="product-match-card__error">{approvalError}</p>}

          <button
            type="button"
            className="btn btn--primary"
            onClick={handleApproveClick}
            disabled={!pendingCandidate || isApproving}
          >
            {isApproving ? 'Confirming match…' : 'Confirm Product Match'}
          </button>
        </div>
      )}
    </article>
  )
}

export default ProductMatchCard
