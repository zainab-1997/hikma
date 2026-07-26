import { useEffect, useState } from 'react'
import AppIcon from '../ui/AppIcon'
import IconButton from '../ui/IconButton'
import Sidebar from './Sidebar'
import Topbar from './Topbar'

const APP_VERSION = import.meta.env.VITE_APP_VERSION || '1.0.0-rc1'

function AppShell({ activeView, onViewChange, children }) {
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [systemStatus, setSystemStatus] = useState('Checking system')

  useEffect(() => {
    if (!drawerOpen) return undefined
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') setDrawerOpen(false)
    }
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [drawerOpen])

  const navigate = (view) => {
    onViewChange(view)
    setDrawerOpen(false)
  }

  return (
    <div className={`app-shell ${drawerOpen ? 'app-shell--drawer-open' : ''}`}>
      <div className="app-shell__desktop-sidebar">
        <Sidebar activeView={activeView} onNavigate={navigate} status={systemStatus} version={APP_VERSION} />
      </div>
      <div className="app-shell__drawer" aria-hidden={!drawerOpen} inert={!drawerOpen}>
        <div className="app-shell__drawer-head">
          <span>Navigation</span>
          <IconButton label="Close navigation" onClick={() => setDrawerOpen(false)}><AppIcon name="close" /></IconButton>
        </div>
        <Sidebar activeView={activeView} onNavigate={navigate} status={systemStatus} version={APP_VERSION} />
      </div>
      <button type="button" className="app-shell__overlay" aria-label="Close navigation"
        tabIndex={drawerOpen ? 0 : -1} onClick={() => setDrawerOpen(false)} />
      <div className="app-shell__main">
        <Topbar activeView={activeView} onOpenMenu={() => setDrawerOpen(true)} onStatusChange={setSystemStatus} />
        {children}
      </div>
    </div>
  )
}

export default AppShell
