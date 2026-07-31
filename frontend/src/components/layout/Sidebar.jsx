import AppIcon from '../ui/AppIcon'
import { NAVIGATION } from './navigation'

function Sidebar({ activeView, onNavigate, status, version }) {
  return (
    <aside className="sidebar" aria-label="Primary navigation">
      <div className="sidebar__brand">
        <span className="sidebar__brand-mark"><AppIcon name="package" size={24} /></span>
        <span className="sidebar__brand-copy">
          <strong>Hikma Order</strong>
          <span>Automation Platform</span>
        </span>
      </div>
      <nav className="sidebar__nav" aria-label="Application">
        <span className="sidebar__nav-label">Workspace</span>
        {NAVIGATION.map((item) => (
          <button key={item.id} type="button"
            className={`sidebar__nav-item ${activeView === item.id ? 'sidebar__nav-item--active' : ''}`}
            aria-current={activeView === item.id ? 'page' : undefined}
            onClick={() => onNavigate(item.id)}>
            <AppIcon name={item.icon} size={19} />
            <span>{item.label}</span>
          </button>
        ))}
      </nav>
      <div className="sidebar__footer">
        <div className="sidebar__system">
          <AppIcon name="activity" size={17} />
          <div><span>System status</span><strong>{status}</strong></div>
        </div>
        <span className="sidebar__version">Version {version}</span>
      </div>
    </aside>
  )
}

export default Sidebar
