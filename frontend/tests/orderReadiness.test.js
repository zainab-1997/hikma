import test from 'node:test'
import assert from 'node:assert/strict'

import { getOrderReadiness } from '../src/utils/orderReadiness.js'

const matchedOrder = {
  products: [{ match_status: 'matched' }],
}

test('optional informational notices do not disable generation', () => {
  const review = {
    blocking_errors: [],
    required_confirmations: [],
    missing_information: [],
    informational_notices: [
      { type: 'optional_information_missing', message: 'Optional information not provided: Governorate.' },
    ],
  }

  assert.equal(getOrderReadiness(review, matchedOrder).canGenerate, true)
})

test('blocking backend errors disable generation', () => {
  const review = {
    blocking_errors: [{ type: 'missing_required_field', message: 'Customer name is required.' }],
    required_confirmations: [],
    missing_information: ['customer_name'],
    informational_notices: [],
  }

  const readiness = getOrderReadiness(review, matchedOrder)
  assert.equal(readiness.canGenerate, false)
  assert.ok(readiness.blockingCount > 0)
})

test('unresolved product matches still disable generation', () => {
  const review = {
    blocking_errors: [],
    required_confirmations: [],
    missing_information: [],
    informational_notices: [],
  }
  const unresolved = { products: [{ match_status: 'ambiguous' }] }

  assert.equal(getOrderReadiness(review, unresolved).canGenerate, false)
})
