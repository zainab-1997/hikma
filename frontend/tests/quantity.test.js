import assert from 'node:assert/strict'
import test from 'node:test'

import { formatQuantityInput, parseOrderQuantity } from '../src/utils/quantity.js'

test('parsed quantity is preserved while genuinely missing quantity stays empty', () => {
  assert.equal(formatQuantityInput(20), '20')
  assert.equal(formatQuantityInput(null), '')
  assert.equal(formatQuantityInput(undefined), '')
})

test('missing quantity remains empty and required', () => {
  assert.deepEqual(parseOrderQuantity(''), {
    value: null,
    error: 'Quantity is required / الكمية مطلوبة',
  })
})

test('English, Arabic, and Persian digits produce the same integer quantity', () => {
  assert.equal(parseOrderQuantity('20').value, 20)
  assert.equal(parseOrderQuantity('٢٠').value, 20)
  assert.equal(parseOrderQuantity('۲۰').value, 20)
})

test('zero, decimals, text, and excessive quantities are rejected', () => {
  for (const input of ['0', '1.5', 'abc', '1000001']) {
    assert.equal(parseOrderQuantity(input).value, null)
    assert.ok(parseOrderQuantity(input).error)
  }
})
