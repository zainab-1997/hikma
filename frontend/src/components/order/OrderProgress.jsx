import AppIcon from '../ui/AppIcon'

const STEPS = ['Message', 'Details', 'Products', 'Confirm', 'Generated']

function OrderProgress({ currentStep, processingLabel }) {
  return (
    <section className="order-rail-card" aria-labelledby="order-progress-title">
      <div className="order-rail-card__heading">
        <AppIcon name="activity" size={17} />
        <h2 id="order-progress-title">Order progress</h2>
      </div>
      <ol className="order-progress">
        {STEPS.map((label, index) => {
          const state = index < currentStep ? 'complete' : index === currentStep ? 'current' : 'upcoming'
          return (
            <li key={label} className={`order-progress__step order-progress__step--${state}`}
              aria-current={state === 'current' ? 'step' : undefined}>
              <span className="order-progress__marker">{state === 'complete' ? '✓' : index + 1}</span>
              <span><strong>{label}</strong><small>{state === 'complete' ? 'Complete' : state === 'current' ? 'In progress' : 'Not started'}</small></span>
            </li>
          )
        })}
      </ol>
      {processingLabel && <p className="order-progress__activity" aria-live="polite">{processingLabel}</p>}
    </section>
  )
}

export default OrderProgress
