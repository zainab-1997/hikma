import { useEffect, useRef } from 'react'

function Modal({ title, description, onClose, children, footer, size = 'medium' }) {
  const closeRef = useRef(null)
  const titleId = `modal-title-${title.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`
  const descriptionId = description ? `${titleId}-description` : undefined

  useEffect(() => {
    const previousFocus = document.activeElement
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    closeRef.current?.focus()
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', handleKeyDown)
      previousFocus?.focus?.()
    }
  }, [onClose])

  return (
    <div className="modal-overlay" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className={`modal-card modal-card--${size}`} role="dialog" aria-modal="true"
        aria-labelledby={titleId} aria-describedby={descriptionId}>
        <header className="modal-card__header">
          <div><h2 id={titleId}>{title}</h2>{description && <p id={descriptionId}>{description}</p>}</div>
          <button ref={closeRef} type="button" className="modal-card__close" onClick={onClose} aria-label={`Close ${title}`}>
            <span aria-hidden="true">×</span>
          </button>
        </header>
        <div className="modal-card__body">{children}</div>
        {footer && <footer className="modal-card__footer">{footer}</footer>}
      </section>
    </div>
  )
}

export default Modal
