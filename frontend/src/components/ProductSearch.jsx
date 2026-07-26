import { useState } from 'react'
import { searchProducts } from '../services/api'

function ProductSearch({ onSelect }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState(null)
  const [isSearching, setIsSearching] = useState(false)
  const [error, setError] = useState('')

  const handleSearch = async (event) => {
    event.preventDefault()
    if (!query.trim()) return

    setIsSearching(true)
    setError('')

    try {
      const products = await searchProducts(query.trim())
      setResults(products)
    } catch (err) {
      setError(err.message || 'Product search failed. Please try again.')
      setResults(null)
    } finally {
      setIsSearching(false)
    }
  }

  return (
    <div className="product-search">
      <form className="product-search__form" onSubmit={handleSearch}>
        <label className="sr-only" htmlFor="official-product-search">Search the official product catalog</label>
        <input
          id="official-product-search"
          type="text"
          className="field__input"
          dir="auto"
          placeholder="Search official products..."
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <button type="submit" className="btn btn--secondary" disabled={isSearching}>
          {isSearching ? 'Searching...' : 'Search'}
        </button>
      </form>

      {isSearching && <p className="product-search__status" role="status">Searching the official catalog…</p>}
      {error && <p className="product-search__error" role="alert">{error}</p>}

      {results && (
        <ul className="product-search__results" aria-label="Official product search results">
          {results.length === 0 && <li className="product-search__empty">No products found.</li>}
          {results.map((product) => (
            <li key={product.row}>
              <button type="button" className="candidate-option" dir="auto" onClick={() => onSelect(product)}>
                {product.official_name}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default ProductSearch
