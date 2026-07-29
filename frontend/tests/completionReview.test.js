import assert from 'node:assert/strict'
import test from 'node:test'

import { buildCompactCompletionRows } from '../src/utils/completionReview.js'

test('completion page contains only the four requested metadata rows', () => {
  const rows = buildCompactCompletionRows({
    order_number: 'HIK-100',
    filename: 'order.xlsx',
    selected_order_total: 190000,
  }, 'Pharmacy Price')

  assert.deepEqual(rows, [
    ['Order Number', 'HIK-100'],
    ['Filename', 'order.xlsx'],
    ['Selected Price Type', 'Pharmacy Price'],
    ['Order Total', '190,000 IQD'],
  ])
})
