import { lazy, Suspense, useRef, useState } from 'react'
import AppShell from './components/layout/AppShell'
import OrderInput from './components/OrderInput'
import OrderPreview from './components/OrderPreview'
import StatusMessage from './components/StatusMessage'
import OrderProgress from './components/order/OrderProgress'
import OrderSummaryCard from './components/order/OrderSummaryCard'
import { applyBusinessRules, generateExcelOrder, matchProducts, parseOrder, selectProduct } from './services/api'
import { getOrderReadiness } from './utils/orderReadiness'
import './styles/app.css'
import './styles/components.css'

const OrderHistory = lazy(() => import('./components/OrderHistory'))
const AnalyticsDashboard = lazy(() => import('./pages/AnalyticsDashboard'))

function PageSkeleton() {
  return <div className="page-skeleton" role="status" aria-label="Loading page">
    <span /><span /><span /><span />
  </div>
}

function describeError(error) {
  if (error instanceof TypeError) {
    return 'Backend unavailable. Please make sure the server is running and try again.'
  }
  return error.message || 'Something went wrong. Please try again.'
}

function App() {
  const [view, setView] = useState('new')
  const [message, setMessage] = useState('')

  // Pipeline state, kept separate on purpose. originalParsedOrder never drives rendering
  // (nothing displays it — it exists so the exact AI output is preserved even after the
  // user edits fields), so it's a ref rather than state.
  const originalParsedOrderRef = useRef(null) // untouched /parse output
  const generationAttemptRef = useRef({ fingerprint: null, requestId: null, inFlight: false })
  const validationRequestRef = useRef(0)
  const [editableOrder, setEditableOrder] = useState(null) // user-editable structured order sent to apply-rules / match-products
  const [reviewResult, setReviewResult] = useState(null) // business-rules output
  const [matchResult, setMatchResult] = useState(null) // product-matching output
  const [approvedSelections, setApprovedSelections] = useState({}) // { [productIndex]: { row, official_name } }

  const [priceTypeOverride, setPriceTypeOverride] = useState(null)
  const [status, setStatus] = useState({ type: '', message: '' })
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [processingStage, setProcessingStage] = useState('')
  const [isReapplying, setIsReapplying] = useState(false)
  const [approvingIndex, setApprovingIndex] = useState(null)
  const [approvalErrors, setApprovalErrors] = useState({})

  const [isGenerating, setIsGenerating] = useState(false)
  const [generatedOrder, setGeneratedOrder] = useState(null) // GeneratedOrderResponse from /generate-excel

  const textareaRef = useRef(null)

  const resetReview = () => {
    originalParsedOrderRef.current = null
    setEditableOrder(null)
    setReviewResult(null)
    setMatchResult(null)
    setApprovedSelections({})
    setApprovalErrors({})
    setPriceTypeOverride(null)
    setGeneratedOrder(null)
    setProcessingStage('')
  }

  const handleAnalyze = async () => {
    if (!message.trim()) {
      setStatus({ type: 'error', message: 'Please paste a WhatsApp order message first.' })
      resetReview()
      return
    }

    setStatus({ type: '', message: '' })
    resetReview()
    setIsAnalyzing(true)

    try {
      setProcessingStage('Reading order details…')
      const parsed = await parseOrder(message)
      originalParsedOrderRef.current = parsed
      setEditableOrder(parsed)

      setProcessingStage('Applying business rules…')
      const review = await applyBusinessRules({ ...parsed, price_type_override: null })
      setReviewResult(review)

      setProcessingStage('Matching products…')
      const matched = await matchProducts(review)
      setMatchResult(matched)
    } catch (error) {
      setStatus({ type: 'error', message: describeError(error) })
    } finally {
      setIsAnalyzing(false)
      setProcessingStage('')
    }
  }

  const handleReapply = async () => {
    if (!editableOrder) return

    setStatus({ type: '', message: '' })
    setGeneratedOrder(null)
    setApprovedSelections({})
    setIsReapplying(true)

    try {
      setProcessingStage('Applying updated business rules…')
      const review = await applyBusinessRules({ ...editableOrder, price_type_override: priceTypeOverride })
      setReviewResult(review)

      setProcessingStage('Refreshing product matches…')
      const matched = await matchProducts(review)
      setMatchResult(matched)
    } catch (error) {
      setStatus({ type: 'error', message: describeError(error) })
    } finally {
      setIsReapplying(false)
      setProcessingStage('')
    }
  }

  const handleCustomerFieldChange = (field, value) => {
    setEditableOrder((prev) => {
      if (!prev) return prev
      const transitField = {
        governorate: 'destination_governorate',
        city: 'destination_city',
        area: 'destination_area',
      }[field]
      return {
        ...prev,
        customer: { ...prev.customer, [field]: value },
        transit: transitField && prev.transit.is_transit
          ? { ...prev.transit, [transitField]: value }
          : prev.transit,
      }
    })
  }

  const handleTransitFieldChange = (field, value) => {
    setEditableOrder((prev) => prev && { ...prev, transit: { ...prev.transit, [field]: value } })
  }

  const handleProductFieldChange = async (index, field, value) => {
    if (!editableOrder) return
    const products = editableOrder.products.map((product, i) =>
      i === index ? { ...product, [field]: value } : product,
    )
    const nextOrder = { ...editableOrder, products }
    setEditableOrder(nextOrder)
    setGeneratedOrder(null)
    setApprovedSelections({})

    const requestNumber = validationRequestRef.current + 1
    validationRequestRef.current = requestNumber
    setIsReapplying(true)
    try {
      const review = await applyBusinessRules({
        ...nextOrder,
        price_type_override: priceTypeOverride,
      })
      const matched = await matchProducts(review)
      if (validationRequestRef.current === requestNumber) {
        setReviewResult(review)
        setMatchResult(matched)
        setStatus({ type: '', message: '' })
      }
    } catch (error) {
      if (validationRequestRef.current === requestNumber) {
        setStatus({ type: 'error', message: describeError(error) })
      }
    } finally {
      if (validationRequestRef.current === requestNumber) {
        setIsReapplying(false)
      }
    }
  }

  const handleApproveSelection = async (index, candidate) => {
    setApprovalErrors((prev) => ({ ...prev, [index]: '' }))
    setApprovingIndex(index)

    try {
      const validated = await selectProduct(
        candidate.row,
        candidate.official_name,
        matchResult?.products[index]?.written_product_name,
      )
      setApprovedSelections((prev) => ({ ...prev, [index]: validated }))
    } catch (error) {
      setApprovalErrors((prev) => ({ ...prev, [index]: describeError(error) }))
    } finally {
      setApprovingIndex(null)
    }
  }

  const handleEdit = () => {
    textareaRef.current?.focus()
  }

  const handleNewOrder = () => {
    const hasReviewedState = Boolean(editableOrder || reviewResult || matchResult || generatedOrder)
    if (hasReviewedState && !window.confirm('Start a new order? The current on-screen review will be cleared. Saved orders and files will not be deleted.')) {
      return
    }
    setMessage('')
    setStatus({ type: '', message: '' })
    resetReview()
    window.setTimeout(() => textareaRef.current?.focus(), 0)
  }

  const { canGenerate: canConfirm } = getOrderReadiness(
    reviewResult,
    matchResult,
    approvedSelections,
  )

  const progressStep = generatedOrder
    ? 4
    : matchResult
      ? (canConfirm ? 3 : 2)
      : reviewResult
        ? 2
        : editableOrder
          ? 1
          : 0

  const buildGenerateOrderRequest = (clientRequestId) => {
    const products = matchResult.products.map((product, index) => {
      const approved = approvedSelections[index]
      return {
        written_product_name: product.written_product_name,
        matched_row: approved?.row ?? product.matched_row,
        matched_official_name: approved?.official_name ?? product.matched_official_name,
        quantity: product.quantity,
        free_quantity: product.free_quantity,
        free_percentage: product.free_percentage ?? null,
        notes: product.notes || null,
        match_status: approved ? 'manual' : product.match_status,
        match_score: approved ? approved.score : product.match_score,
      }
    })

    return {
      order_title: reviewResult.order_title,
      selected_price_type: reviewResult.price_type,
      products,
      required_confirmations_resolved: canConfirm,
      order_notes: reviewResult.order_notes,
      customer_name: reviewResult.customer.customer_name,
      customer_type: reviewResult.customer.customer_type,
      governorate: reviewResult.customer.governorate,
      city: reviewResult.customer.city,
      area: reviewResult.customer.area,
      phone_number: reviewResult.customer.phone_number,
      is_transit: reviewResult.transit.is_transit,
      primary_customer: reviewResult.transit.primary_customer,
      destination_customer: reviewResult.transit.destination_customer,
      source_location: reviewResult.transit.source_location,
      destination_location: reviewResult.transit.destination_location,
      destination_governorate: reviewResult.transit.destination_governorate,
      destination_city: reviewResult.transit.destination_city,
      destination_area: reviewResult.transit.destination_area,
      source_message: message,
      parser_confidence_score: reviewResult.confidence_score,
      client_request_id: clientRequestId,
    }
  }

  const handleConfirm = async () => {
    if (
      !canConfirm
      || !reviewResult
      || !matchResult
      || generationAttemptRef.current.inFlight
    ) return

    setStatus({ type: '', message: '' })
    setGeneratedOrder(null)
    setIsGenerating(true)

    const requestWithoutId = buildGenerateOrderRequest(null)
    const fingerprint = JSON.stringify(requestWithoutId)
    const clientRequestId = generationAttemptRef.current.fingerprint === fingerprint
      ? generationAttemptRef.current.requestId
      : crypto.randomUUID()
    generationAttemptRef.current = { fingerprint, requestId: clientRequestId, inFlight: true }

    try {
      const generated = await generateExcelOrder(buildGenerateOrderRequest(clientRequestId))
      setGeneratedOrder(generated)
      setStatus({ type: 'success', message: `Order ${generated.order_number} saved successfully.` })
      // A later intentional submission, even with identical contents, is a new order.
      generationAttemptRef.current = { fingerprint: null, requestId: null, inFlight: false }
    } catch (error) {
      setStatus({ type: 'error', message: describeError(error) })
    } finally {
      generationAttemptRef.current.inFlight = false
      setIsGenerating(false)
    }
  }

  return (
    <AppShell activeView={view} onViewChange={setView}>
      <main key={view} className={`app__main app__main--${view} app__main--entering`}>
        {view === 'new' ? (
          <div className="new-order-workspace">
            <div className="new-order-workspace__main">
              <div className="new-order-intro">
                <span className="new-order-intro__eyebrow">Guided order processing</span>
                <h2>Turn a customer message into an approved order</h2>
                <p>Review every extracted detail and product match before generating the company Excel order.</p>
              </div>
              <OrderInput ref={textareaRef} value={message} onChange={setMessage} onAnalyze={handleAnalyze}
                onClear={handleNewOrder} isLoading={isAnalyzing} processingStage={processingStage} />
              <StatusMessage type={status.type} message={status.message} onRetry={status.type === 'error' ? handleAnalyze : undefined} />
              <OrderPreview
                editableOrder={editableOrder}
                reviewResult={reviewResult}
                matchResult={matchResult}
                priceTypeOverride={priceTypeOverride}
                approvedSelections={approvedSelections}
                approvingIndex={approvingIndex}
                approvalErrors={approvalErrors}
                onCustomerFieldChange={handleCustomerFieldChange}
                onTransitFieldChange={handleTransitFieldChange}
                onProductFieldChange={handleProductFieldChange}
                onPriceTypeOverrideChange={setPriceTypeOverride}
                onApproveSelection={handleApproveSelection}
                onReapply={handleReapply}
                isReapplying={isReapplying}
                onEdit={handleEdit}
                onConfirm={handleConfirm}
                canConfirm={canConfirm}
                isGenerating={isGenerating}
                generatedOrder={generatedOrder}
                onNewOrder={handleNewOrder}
              />
            </div>
            <aside className="new-order-workspace__rail">
              <OrderProgress currentStep={progressStep} processingLabel={processingStage} />
              <OrderSummaryCard reviewResult={reviewResult} matchResult={matchResult} approvedSelections={approvedSelections} />
              <section className="order-safety-note">
                <strong>Safe order generation</strong>
                <p>Every product must be confirmed before generation. The source company workbook is preserved.</p>
              </section>
            </aside>
          </div>
        ) : view === 'history' ? (
          <Suspense fallback={<PageSkeleton />}><OrderHistory /></Suspense>
        ) : (
          <Suspense fallback={<PageSkeleton />}><AnalyticsDashboard /></Suspense>
        )}
      </main>
    </AppShell>
  )
}

export default App
