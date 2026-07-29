import { useState } from 'react'
import EmailOrderPanel from './EmailOrderPanel'
import AppIcon from './ui/AppIcon'
import { resolveApiUrl } from '../services/api'
import { buildCompactCompletionRows, buildGeneratedOrderReview } from '../utils/completionReview'

function formatPriceType(priceType) {
  if (priceType === 'pharmacy') return 'Pharmacy Price'
  if (priceType === 'drug_store') return 'Drug Store Price'
  return 'Unknown'
}

function borderStyle(style) {
  if (!style) return undefined
  const width = style === 'medium' || style === 'thick' ? 2 : 1
  return `${width}px solid #64748b`
}

function ExcelGrid({ preview }) {
  return <div className="excel-preview-shell">
    <div className="excel-preview-sheet-name">{preview.sheet_name}</div>
    <div className="excel-preview-scroll">
      <table className="excel-preview-grid">
        <colgroup>{preview.column_widths.map((width, index) =>
          <col key={index} style={{ width: `${Math.max(70, Number(width || 12) * 7)}px` }} />)}
        </colgroup>
        <tbody>{preview.rows.map((row) => <tr key={row.row}
          style={row.height ? { height: `${row.height}px` } : undefined}>
          {row.cells.map((cell) => <td key={cell.column} colSpan={cell.colspan}
            title={cell.formula || undefined}
            style={{
              backgroundColor: cell.fill_color ? `#${cell.fill_color}` : undefined,
              color: cell.font_color ? `#${cell.font_color}` : undefined,
              fontWeight: cell.font_bold ? 700 : undefined,
              textAlign: cell.horizontal_alignment || undefined,
              borderTop: borderStyle(cell.border_top),
              borderRight: borderStyle(cell.border_right),
              borderBottom: borderStyle(cell.border_bottom),
              borderLeft: borderStyle(cell.border_left),
            }}>
            {cell.value == null ? '' : typeof cell.value === 'number'
              ? cell.value.toLocaleString()
              : cell.value}
          </td>)}
        </tr>)}</tbody>
      </table>
    </div>
  </div>
}

function PreviewModal({ generatedOrder, onClose }) {
  const preview = generatedOrder.workbook_preview
  return <div className="order-preview-modal-backdrop" role="presentation" onMouseDown={(event) => {
    if (event.target === event.currentTarget) onClose()
  }}>
    <section className="order-preview-modal order-preview-modal--workbook" role="dialog"
      aria-modal="true" aria-labelledby="preview-modal-title">
      <header>
        <div><span className="generated-order__saved">Read-only workbook</span>
          <h2 id="preview-modal-title">Excel Preview</h2></div>
        <button type="button" className="modal-close-button" onClick={onClose}
          aria-label="Close preview">×</button>
      </header>
      <div className="order-preview-modal__content">
        <ExcelGrid preview={preview} />
      </div>
      <footer>
        <span>Workbook fingerprint: {preview.workbook_sha256.slice(0, 12)}…</span>
        <a className="btn btn--primary" href={resolveApiUrl(generatedOrder.download_url)}
          download={generatedOrder.filename}>
          <AppIcon name="download" size={17} /> Download Excel
        </a>
      </footer>
    </section>
  </div>
}

function OrderItemsTable({ items }) {
  return <section className="generated-review-section">
    <h3>Order Items</h3>
    <div className="generated-items-scroll">
      <table className="generated-items-table">
        <thead><tr><th>Product</th><th>Quantity</th><th>Bonus</th><th>Match Status</th></tr></thead>
        <tbody>{items.map((item, index) => <tr key={`${item.product}-${index}`}>
          <td dir="auto"><strong>{item.product}</strong></td>
          <td>{item.quantity.toLocaleString()}</td>
          <td>{item.bonus ? item.bonus.toLocaleString() : '—'}</td>
          <td><span className={`generated-match-status generated-match-status--${item.statusKey}`}>
            {item.status}
          </span></td>
        </tr>)}</tbody>
      </table>
    </div>
  </section>
}

function CompactOrderSummary({ totals }) {
  return <section className="generated-review-section">
    <h3>Order Summary</h3>
    <dl className="generated-summary-grid">
      <div><dt>Products</dt><dd>{totals.products}</dd></div>
      <div><dt>Total Quantity</dt><dd>{totals.quantity.toLocaleString()}</dd></div>
      <div><dt>Total Bonus</dt><dd>{totals.bonus.toLocaleString()}</dd></div>
      <div><dt>Order Total</dt><dd>{totals.orderTotal.toLocaleString()} IQD</dd></div>
    </dl>
  </section>
}

function MatchStatistics({ counts }) {
  const rows = [
    ['Automatically Matched', counts.automatic],
    ['Manually Selected', counts.manual],
    ['Unmatched', counts.unmatched],
    ...(counts.strengthConflict ? [['Strength Conflicts', counts.strengthConflict]] : []),
    ...(counts.ambiguous ? [['Ambiguous Matches', counts.ambiguous]] : []),
  ]
  return <section className="generated-review-section generated-processing-review">
    <h3>Processing Review</h3>
    <dl>{rows.map(([name, value]) => <div key={name}><dt>{name}</dt><dd>{value}</dd></div>)}</dl>
  </section>
}

function GeneratedOrderReview({
  generatedOrder,
  reviewResult,
  matchResult,
  approvedSelections,
  onNewOrder,
}) {
  const [showPreview, setShowPreview] = useState(false)
  const completionRows = buildCompactCompletionRows(
    generatedOrder,
    formatPriceType(generatedOrder.selected_price_type),
  )
  const review = buildGeneratedOrderReview({
    generatedOrder,
    reviewResult,
    matchResult,
    approvedSelections,
  })
  if (!generatedOrder.workbook_preview) return null

  return <>
    <section className="generated-order-success" aria-live="polite">
      <div className="generated-order-success__icon"><AppIcon name="success" size={30} /></div>
      <div className="generated-order-success__body">
        <span className="generated-order__saved">Generated and saved</span>
        <h2>Order generated successfully</h2>
        <p>The approved workbook is ready to preview, download, or send by email.</p>
        <dl className="generated-order__details">
          {review.customerName && <div className="generated-order__row">
            <dt>Customer Name</dt><dd dir="auto">{review.customerName}</dd>
          </div>}
          {review.area && <div className="generated-order__row">
            <dt>Area / City</dt><dd dir="auto">{review.area}</dd>
          </div>}
          {completionRows.map(([name, value]) => <div className="generated-order__row" key={name}>
            <dt>{name}</dt><dd dir={['Filename', 'Order Title'].includes(name) ? 'auto' : undefined}>{value}</dd>
          </div>)}
        </dl>
        <OrderItemsTable items={review.items} />
        <div className="generated-review-footer-grid">
          <CompactOrderSummary totals={review.totals} />
          <MatchStatistics counts={review.statusCounts} />
        </div>
        <div className="generated-order-success__actions">
          <button type="button" className="btn btn--secondary" onClick={() => setShowPreview(true)}>
            Preview Excel
          </button>
          <a className="btn btn--primary" href={resolveApiUrl(generatedOrder.download_url)}
            download={generatedOrder.filename}>
            <AppIcon name="download" size={17} /> Download Excel
          </a>
          <button type="button" className="btn btn--ghost" onClick={onNewOrder}>Process New Order</button>
        </div>
      </div>
    </section>
    <EmailOrderPanel orderId={generatedOrder.order_id} orderNumber={generatedOrder.order_number}
      generatedFilename={generatedOrder.filename} />
    {showPreview && <PreviewModal generatedOrder={generatedOrder} onClose={() => setShowPreview(false)} />}
  </>
}

export default GeneratedOrderReview
