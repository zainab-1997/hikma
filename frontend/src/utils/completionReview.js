export function buildCompactCompletionRows(generatedOrder, formattedPriceType) {
  return [
    ['Order Number', generatedOrder.order_number],
    ...(generatedOrder.order_title ? [['Order Title', generatedOrder.order_title]] : []),
    ['Filename', generatedOrder.filename],
    ['Selected Price Type', formattedPriceType],
    ['Order Total', `${generatedOrder.selected_order_total.toLocaleString()} IQD`],
  ]
}

function displayStatus(product, manuallySelected) {
  if (manuallySelected) return 'Manually Selected'
  if (product.match_status === 'matched') return 'Matched'
  return product.match_status
    ? product.match_status.split('_').map((part) =>
      part.charAt(0).toUpperCase() + part.slice(1)).join(' ')
    : 'Unmatched'
}

export function buildGeneratedOrderReview({
  generatedOrder,
  reviewResult,
  matchResult,
  approvedSelections,
}) {
  const items = matchResult.products.map((product, index) => {
    const approved = approvedSelections[index]
    return {
      product: approved?.official_name || product.matched_official_name || product.written_product_name,
      quantity: Number(product.quantity || 0),
      bonus: Number(product.free_quantity || 0),
      status: displayStatus(product, Boolean(approved)),
      statusKey: approved ? 'manual' : product.match_status || 'unmatched',
    }
  })

  const statusCounts = {
    automatic: items.filter((item) => item.statusKey === 'matched').length,
    manual: items.filter((item) => item.statusKey === 'manual').length,
    unmatched: items.filter((item) => item.statusKey === 'unmatched').length,
    strengthConflict: items.filter((item) => item.statusKey === 'strength_conflict').length,
    ambiguous: items.filter((item) => item.statusKey === 'ambiguous').length,
  }

  return {
    customerName: reviewResult.customer.customer_name,
    area: reviewResult.customer.area || reviewResult.customer.governorate || null,
    items,
    totals: {
      products: items.length,
      quantity: items.reduce((total, item) => total + item.quantity, 0),
      bonus: items.reduce((total, item) => total + item.bonus, 0),
      orderTotal: generatedOrder.selected_order_total,
    },
    statusCounts,
  }
}
