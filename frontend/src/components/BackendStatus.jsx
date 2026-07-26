import { useCallback, useEffect, useRef, useState } from 'react'
import { checkBackendHealth } from '../services/api'
import AppIcon from './ui/AppIcon'
import IconButton from './ui/IconButton'
import StatusIndicator from './ui/StatusIndicator'

function BackendStatus({ onStatusChange }) {
  const [status, setStatus] = useState('checking')
  const mountedRef = useRef(true)

  const checkStatus = useCallback(async (showChecking = false) => {
    if (showChecking && mountedRef.current) setStatus('checking')
    try {
      await checkBackendHealth()
      if (!mountedRef.current) return
      setStatus('connected')
      onStatusChange?.('System online')
    } catch {
      if (!mountedRef.current) return
      setStatus('unavailable')
      onStatusChange?.('System unavailable')
    }
  }, [onStatusChange])

  useEffect(() => {
    mountedRef.current = true
    Promise.resolve().then(checkStatus)
    const timer = window.setInterval(checkStatus, 45000)
    return () => { mountedRef.current = false; window.clearInterval(timer) }
  }, [checkStatus])

  const label =
    status === 'connected'
      ? 'System online'
      : status === 'unavailable'
        ? 'System unavailable'
        : 'Checking system'

  return (
    <StatusIndicator status={status} label={label}
      action={status === 'unavailable' ? (
        <IconButton label="Retry system check" className="status-indicator__retry" onClick={() => checkStatus(true)}>
          <AppIcon name="refresh" size={14} />
        </IconButton>
      ) : null} />
  )
}

export default BackendStatus
