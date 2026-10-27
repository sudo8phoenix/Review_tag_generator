import { Link, NavLink, Outlet, useMatch } from 'react-router-dom'
import { Icon } from './Icon'

const items = [
  { label: 'Saved products', to: '/products', icon: 'bookmark' },
  { label: 'Compare products', to: '/compare', icon: 'compare' },
  { label: 'Browser companion', to: '/companion', icon: 'browser' },
] as const

export function AppShell() {
  const match = useMatch('/products/:id/*')
  const productId = match?.params.id
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <header className="site-header">
        <div className="header-inner">
          <Link className="brand" to="/products" aria-label="Review Tag Generator home">
            <span className="brand-mark" aria-hidden="true">R</span>
            <span className="brand-text">Review <span>Tag Generator</span></span>
          </Link>
          <div className="header-note"><span className="connection-dot" aria-hidden="true" /> Your shopping companion <span className="local-label">Local workspace</span></div>
        </div>
      </header>
      <div className="workspace-layout">
        <nav className="site-nav" aria-label="Primary navigation">
          <p className="nav-caption">Your collection</p>
          <ul>
            {items.map((item) => (
              <li key={item.label}>
                <NavLink
                  to={item.to}
                  className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
                >
                  <Icon name={item.icon} /><span>{item.label}</span>
                </NavLink>
              </li>
            ))}
          </ul>
          {productId && <div className="product-nav"><p className="nav-caption">This product</p><ul>
            <li><NavLink className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`} to={`/products/${productId}`} end>Overview</NavLink></li>
            <li><NavLink className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`} to={`/products/${productId}/review`}>Analyze review</NavLink></li>
            <li><NavLink className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`} to={`/products/${productId}/upload`}>Import reviews</NavLink></li>
          </ul></div>}
          <div className="nav-bottom"><p className="nav-caption">Advanced</p><NavLink to="/models" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}><Icon name="sliders" /><span>Model metrics</span></NavLink><p className="nav-footer">A little more evidence.<br />A more considered purchase.</p><span className="nav-version">REVIEW TAG GENERATOR · LOCAL</span></div>
        </nav>
        <main id="main-content" className="main-content" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
    </div>
  )
}
