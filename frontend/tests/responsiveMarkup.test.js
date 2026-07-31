import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')

test('mobile navigation exposes accessible expanded and controlled state', () => {
  const topbar = read('../src/components/layout/Topbar.jsx')
  const shell = read('../src/components/layout/AppShell.jsx')

  assert.match(topbar, /aria-expanded=\{menuOpen\}/)
  assert.match(topbar, /aria-controls="mobile-navigation"/)
  assert.match(shell, /id="mobile-navigation"/)
  assert.match(shell, /setDrawerOpen\(false\)/)
})

test('AppShell integrates MobileNavigation with live view state and navigation callback', () => {
  const shell = read('../src/components/layout/AppShell.jsx')

  assert.match(shell, /import MobileNavigation from ['"]\.\/MobileNavigation['"]/)
  assert.match(
    shell,
    /<MobileNavigation\s+activeView=\{activeView\}\s+onViewChange=\{navigate\}\s*\/>/,
  )
  assert.match(shell, /const navigate = \(view\) => \{[\s\S]*onViewChange\(view\)/)
})

test('responsive data tables retain labels when rows become mobile cards', () => {
  const sources = [
    '../src/components/OrderHistory.jsx',
    '../src/components/GeneratedOrderReview.jsx',
    '../src/components/analytics/CustomerAnalyticsTable.jsx',
    '../src/components/analytics/ProductAnalyticsTable.jsx',
    '../src/components/analytics/SalesTrendChart.jsx',
    '../src/components/analytics/SplitAnalytics.jsx',
  ].map(read)

  for (const source of sources) assert.match(source, /data-label=/)
})

test('mobile CSS contains card tables, internal Excel scrolling, and touch targets', () => {
  const css = read('../src/styles/components.css')
  const appCss = read('../src/styles/app.css')

  assert.match(css, /@media \(max-width: 700px\)/)
  assert.match(css, /\.mobile-card-table td::before/)
  assert.match(css, /\.excel-preview-scroll/)
  assert.match(css, /min-height: 44px/)
  assert.match(appCss, /\.topbar__menu-button,[\s\S]*width: 44px/)
})

test('premium mobile shell includes safe areas, bottom navigation, lazy pages, and PWA metadata', () => {
  const app = read('../src/App.jsx')
  const appCss = read('../src/styles/app.css')
  const mobileNavigation = read('../src/components/layout/MobileNavigation.jsx')
  const html = read('../index.html')
  const manifest = JSON.parse(read('../public/manifest.webmanifest'))

  assert.match(app, /lazy\(\(\) => import/)
  assert.match(app, /Suspense/)
  assert.match(appCss, /env\(safe-area-inset-bottom/)
  assert.match(appCss, /@media \(max-width: 700px\)[\s\S]*\.mobile-bottom-nav/)
  assert.match(appCss, /\.mobile-bottom-nav/)
  assert.match(mobileNavigation, /aria-current=/)
  assert.match(html, /viewport-fit=cover/)
  assert.match(html, /manifest\.webmanifest/)
  assert.equal(manifest.display, 'standalone')
})

test('mobile interaction layer provides bottom sheets, sticky actions, and skeletons', () => {
  const css = read('../src/styles/components.css')
  const analyticsSection = read('../src/components/analytics/AnalyticsSection.jsx')

  assert.match(css, /@keyframes sheet-enter/)
  assert.match(css, /\.generate-order-panel[\s\S]*position: sticky/)
  assert.match(css, /@keyframes skeleton-shimmer/)
  assert.match(analyticsSection, /section-skeleton/)
})

test('Excel preview escapes shell clipping and keeps the entire workbook scrollable', () => {
  const review = read('../src/components/GeneratedOrderReview.jsx')
  const css = read('../src/styles/components.css')

  assert.match(review, /createPortal/)
  assert.match(review, /document\.body/)
  assert.match(review, /preview\.max_row/)
  assert.match(review, /preview\.max_column/)
  assert.match(css, /\.excel-preview-scroll[\s\S]*overflow: auto/)
  assert.match(css, /\.excel-preview-grid[\s\S]*width: max-content/)
  assert.match(css, /\.order-preview-modal-backdrop[\s\S]*height: 100dvh/)
})
