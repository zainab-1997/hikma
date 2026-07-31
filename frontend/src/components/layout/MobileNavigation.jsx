import AppIcon from '../ui/AppIcon'
import { NAVIGATION } from './navigation'

function MobileNavigation({ activeView, onViewChange }) {
  return (
    <>
      {activeView !== 'new' && (
        <button type="button" className="mobile-new-order-fab" onClick={() => onViewChange('new')}
          aria-label="Create new order">
          <AppIcon name="plus" size={22} />
        </button>
      )}
      <nav id="mobile-bottom-navigation" className="mobile-bottom-nav" aria-label="Primary mobile navigation">
        {NAVIGATION.map((item) => (
          <button key={item.id} type="button"
            className={activeView === item.id ? 'mobile-bottom-nav__item--active' : ''}
            aria-current={activeView === item.id ? 'page' : undefined}
            onClick={() => onViewChange(item.id)}>
            <AppIcon name={item.icon} size={21} />
            <span>{item.label}</span>
          </button>
        ))}
      </nav>
    </>
  )
}

export default MobileNavigation
