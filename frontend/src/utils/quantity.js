export const MAX_ORDER_QUANTITY = 1_000_000

export function formatQuantityInput(quantity) {
  return quantity == null ? '' : String(quantity)
}

export function parseOrderQuantity(rawValue) {
  const normalized = String(rawValue)
    .replace(/[٠-٩]/g, (digit) => String('٠١٢٣٤٥٦٧٨٩'.indexOf(digit)))
    .replace(/[۰-۹]/g, (digit) => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(digit)))
    .trim()
  if (!normalized) {
    return { value: null, error: 'Quantity is required / الكمية مطلوبة' }
  }
  if (!/^\d+$/.test(normalized)) {
    return { value: null, error: 'Enter a whole number / أدخل عدداً صحيحاً' }
  }
  const value = Number(normalized)
  if (value <= 0 || value > MAX_ORDER_QUANTITY) {
    return {
      value: null,
      error: 'Quantity must be 1–1,000,000 / الكمية يجب أن تكون ضمن الحد المسموح',
    }
  }
  return { value, error: '' }
}
