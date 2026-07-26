function AnalyticsFilters({ options, draft, onChange, onApply, onReset, onRefresh, error, loading }) {
  const field = (name, value) => onChange({ ...draft, [name]: value })
  return (
    <section className="analytics-filters card" aria-labelledby="analytics-filters-title">
      <div className="analytics-section__header analytics-filters__heading">
        <div>
          <h2 id="analytics-filters-title">Global Filters</h2>
          <p>Filters apply only when you choose Apply Filters.</p>
        </div>
        <button type="button" className="btn btn--secondary btn--compact" onClick={onRefresh} disabled={loading}>
          Refresh Dashboard
        </button>
      </div>
      <div className="analytics-filter-grid">
        <label className="field"><span className="field__label">Date From</span>
          <input className="field__input" type="date" value={draft.date_from} onChange={(e) => field('date_from', e.target.value)} />
        </label>
        <label className="field"><span className="field__label">Date To</span>
          <input className="field__input" type="date" value={draft.date_to} onChange={(e) => field('date_to', e.target.value)} />
        </label>
        <label className="field"><span className="field__label">Governorate</span>
          <select className="field__input" value={draft.governorate} onChange={(e) => field('governorate', e.target.value)}>
            <option value="">All governorates</option>
            {options.governorates.map((value) => <option key={value}>{value}</option>)}
          </select>
        </label>
        <label className="field"><span className="field__label">Customer Type</span>
          <select className="field__input" value={draft.customer_type} onChange={(e) => field('customer_type', e.target.value)}>
            <option value="">All customer types</option>
            {options.customer_types.map((value) => <option key={value}>{value}</option>)}
          </select>
        </label>
        <label className="field"><span className="field__label">Price Type</span>
          <select className="field__input" value={draft.selected_price_type} onChange={(e) => field('selected_price_type', e.target.value)}>
            <option value="">All price types</option>
            {options.price_types.map((value) => <option key={value} value={value}>{value === 'pharmacy' ? 'Pharmacy & Hospitals' : value === 'drug_store' ? 'Drug Store' : value}</option>)}
          </select>
        </label>
        <label className="field"><span className="field__label">Customer Name</span>
          <input className="field__input" value={draft.customer_name} onChange={(e) => field('customer_name', e.target.value)} placeholder="Search customer…" />
        </label>
        <label className="field"><span className="field__label">Product Name</span>
          <input className="field__input" value={draft.product_name} onChange={(e) => field('product_name', e.target.value)} placeholder="Search official product…" />
        </label>
      </div>
      {error && <p className="analytics-filter-error" role="alert">{error}</p>}
      <div className="analytics-filter-actions">
        <button type="button" className="btn btn--primary analytics-btn" onClick={onApply}>Apply Filters</button>
        <button type="button" className="btn btn--secondary" onClick={onReset}>Reset Filters</button>
      </div>
    </section>
  )
}

export default AnalyticsFilters
