import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const app = fs.readFileSync(new URL('../src/App.jsx', import.meta.url), 'utf8')
const mobileInput = fs.readFileSync(new URL('../src/components/mobile/MobileOrderInput.jsx', import.meta.url), 'utf8')
const mobileReview = fs.readFileSync(new URL('../src/components/mobile/MobileOrderReview.jsx', import.meta.url), 'utf8')
const styles = fs.readFileSync(new URL('../src/styles/components.css', import.meta.url), 'utf8')

test('App keeps desktop and mobile order compositions separate while sharing workflow state', () => {
  assert.match(app, /className="desktop-new-order-composition"/)
  assert.match(app, /className="mobile-new-order-composition"/)
  assert.match(app, /<MobileOrderInput[\s\S]*onAnalyze=\{handleAnalyze\}/)
  assert.match(app, /<MobileOrderReview[\s\S]*reviewResult=\{reviewResult\}[\s\S]*onConfirm=\{handleConfirm\}/)
})

test('mobile first screen contains only the paste hero and analyze action', () => {
  assert.match(mobileInput, /Paste WhatsApp Order/)
  assert.match(mobileInput, /Analyze Order/)
  assert.doesNotMatch(mobileInput, /OrderProgress|OrderSummaryCard|What happens next|Safe order generation/)
})

test('mobile review is progressive and exposes the three non-wrapping workflow steps', () => {
  assert.match(mobileReview, /if \(!editableOrder \|\| !reviewResult \|\| !matchResult\) return null/)
  assert.match(mobileReview, /\['Parse', 'Review', 'Generate'\]/)
  assert.match(styles, /\.mobile-order-stepper[\s\S]*grid-template-columns: repeat\(3, minmax\(0, 1fr\)\)/)
  assert.match(styles, /\.mobile-order-stepper li[\s\S]*white-space: nowrap/)
})

test('mobile customer review displays existing governorate, city, and area fields', () => {
  assert.match(mobileReview, /value=\{editableOrder\.customer\.governorate \|\| ''\}/)
  assert.match(mobileReview, /value=\{editableOrder\.customer\.city \|\| ''\}/)
  assert.match(mobileReview, /value=\{editableOrder\.customer\.area \|\| ''\}/)
})

test('mobile composition is breakpoint-isolated and desktop composition remains the default', () => {
  assert.match(styles, /\.desktop-new-order-composition\s*\{\s*display: contents;/)
  assert.match(styles, /\.mobile-new-order-composition\s*\{\s*display: none;/)
  assert.match(styles, /@media \(max-width: 700px\)[\s\S]*\.desktop-new-order-composition\s*\{\s*display: none;/)
  assert.match(styles, /@media \(max-width: 700px\)[\s\S]*\.mobile-new-order-composition\s*\{[\s\S]*display: flex;/)
  assert.match(styles, /\.mobile-generate-action[\s\S]*bottom: calc\(74px \+ env\(safe-area-inset-bottom, 0px\)\)/)
})
