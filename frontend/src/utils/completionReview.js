export function buildCompactCompletionRows(generatedOrder, formattedPriceType) {
  return [
    ['Order Number', generatedOrder.order_number],
    ['Filename', generatedOrder.filename],
    ['Selected Price Type', formattedPriceType],
    ['Order Total', `${generatedOrder.selected_order_total.toLocaleString()} IQD`],
  ]
}
