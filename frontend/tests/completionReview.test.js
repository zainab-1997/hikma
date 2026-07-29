import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildCompactCompletionRows,
  buildGeneratedOrderReview,
} from '../src/utils/completionReview.js'

test('completion page displays the same canonical order title', () => {
  const rows = buildCompactCompletionRows({
    order_number: 'HIK-100',
    order_title: 'مذخر ساوة - ترانزيت - مستشفى الكوثر - البصرة',
    filename: 'order.xlsx',
    selected_order_total: 190000,
  }, 'Pharmacy Price')

  assert.deepEqual(rows, [
    ['Order Number', 'HIK-100'],
    ['Order Title', 'مذخر ساوة - ترانزيت - مستشفى الكوثر - البصرة'],
    ['Filename', 'order.xlsx'],
    ['Selected Price Type', 'Pharmacy Price'],
    ['Order Total', '190,000 IQD'],
  ])
})

function reviewFor(products, approvedSelections = {}, customer = {}) {
  return buildGeneratedOrderReview({
    generatedOrder: { selected_order_total: 219450 },
    reviewResult: {
      customer: {
        customer_name: 'Test Pharmacy',
        area: null,
        governorate: null,
        ...customer,
      },
    },
    matchResult: { products },
    approvedSelections,
  })
}

const automaticProduct = (index, overrides = {}) => ({
  written_product_name: `Entered ${index}`,
  matched_official_name: `Official ${index}`,
  match_status: 'matched',
  quantity: index,
  free_quantity: 0,
  ...overrides,
})

test('one-item order uses the final approved name and existing quantities', () => {
  const review = reviewFor([automaticProduct(5, { free_quantity: 2 })])
  assert.deepEqual(review.items[0], {
    product: 'Official 5',
    quantity: 5,
    bonus: 2,
    status: 'Matched',
    statusKey: 'matched',
  })
  assert.deepEqual(review.totals, {
    products: 1,
    quantity: 5,
    bonus: 2,
    orderTotal: 219450,
  })
})

test('multiple products aggregate quantity and bonus without recalculating order total', () => {
  const review = reviewFor([
    automaticProduct(5, { free_quantity: 2 }),
    automaticProduct(10, { free_quantity: null }),
    automaticProduct(3, { free_quantity: 1 }),
  ])
  assert.equal(review.totals.products, 3)
  assert.equal(review.totals.quantity, 18)
  assert.equal(review.totals.bonus, 3)
  assert.equal(review.totals.orderTotal, 219450)
})

test('orders above ten items retain every row for scrolling', () => {
  const products = Array.from({ length: 12 }, (_, index) => automaticProduct(index + 1))
  const review = reviewFor(products)
  assert.equal(review.items.length, 12)
  assert.equal(review.items[11].product, 'Official 12')
})

test('manual selection overrides the candidate name and is counted separately', () => {
  const review = reviewFor(
    [automaticProduct(3, { match_status: 'ambiguous', matched_official_name: null })],
    { 0: { official_name: 'Approved Official Product', row: 14 } },
  )
  assert.equal(review.items[0].product, 'Approved Official Product')
  assert.equal(review.items[0].status, 'Manually Selected')
  assert.equal(review.statusCounts.manual, 1)
  assert.equal(review.statusCounts.automatic, 0)
})

test('missing optional area remains absent while governorate can provide city context', () => {
  assert.equal(reviewFor([automaticProduct(1)]).area, null)
  assert.equal(
    reviewFor([automaticProduct(1)], {}, { governorate: 'Baghdad' }).area,
    'Baghdad',
  )
})
