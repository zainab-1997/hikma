import BackendStatus from '../BackendStatus'
import AppIcon from '../ui/AppIcon'
import IconButton from '../ui/IconButton'

const PAGE_META = {
  new: { title: 'New Order', description: 'Process and approve pharmaceutical orders.' },
  history: { title: 'Order History', description: 'Review generated orders and delivery activity.' },
  analytics: { title: 'Analytics', description: 'Monitor order, customer, and operational performance.' },
}

function Topbar({ activeView, onOpenMenu, onStatusChange, menuOpen }) {
  const page = PAGE_META[activeView]
  return (
    <header className="topbar">
      <div className="topbar__left">
        <IconButton label="Open navigation" className="topbar__menu-button" onClick={onOpenMenu}
          aria-expanded={menuOpen} aria-controls="mobile-navigation">
          <AppIcon name="menu" />
        </IconButton>
        <div className="topbar__titles">
          <h1>{page.title}</h1>
          <p>{page.description}</p>
        </div>
      </div>
      <BackendStatus onStatusChange={onStatusChange} />
    </header>
  )
}

export default Topbar
