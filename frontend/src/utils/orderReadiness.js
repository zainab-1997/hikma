export function getOrderReadiness(reviewResult, matchResult, approvedSelections = {}) {
  if (!reviewResult || !matchResult) {
    return { canGenerate: false, unresolvedProducts: 0, blockingCount: 0 }
  }

  const unresolvedProducts = matchResult.products.filter(
    (product, index) => product.match_status !== 'matched' && !approvedSelections[index],
  ).length
  // missing_information is retained for backward compatibility and normally mirrors
  // blocking_errors. Use it only as a fallback so the same backend issue is not counted twice.
  const requiredFieldErrors = (reviewResult.blocking_errors?.length || 0) ||
    (reviewResult.missing_information?.length || 0)
  const blockingCount =
    requiredFieldErrors +
    (reviewResult.required_confirmations?.length || 0) +
    unresolvedProducts

  return {
    canGenerate: blockingCount === 0,
    unresolvedProducts,
    blockingCount,
  }
}
