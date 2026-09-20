import { NavLink, Outlet } from 'react-router-dom'

const items = [
  { label: 'Products', to: '/products', end: true },
  { label: 'Review analyzer', to: '/products', end: false, selection: true },
  { label: 'Imports', to: '/products', end: false, selection: true },
  { label: 'Model metrics', to: '/models', end: true },
] as const

export function AppShell() {
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <header className="site-header">
        <div className="header-inner">
          <div className="brand" aria-label="Review Tag Generator">
            <span className="brand-mark" aria-hidden="true">R</span>
            <span className="brand-text">Review <span>Tag Generator</span></span>
          </div>
          <span className="header-note">Product review analysis</span>
        </div>
      </header>
      <div className="workspace-layout">
        <nav className="site-nav" aria-label="Primary navigation">
          <p className="nav-caption">Workspace</p>
          <ul>
            {items.map((item) => (
              <li key={item.label}>
                <NavLink
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) => `nav-link${isActive && !('selection' in item) ? ' active' : ''}`}
                >
                  <span>{item.label}</span>
                  {'selection' in item && <span className="nav-hint">Choose a product</span>}
                </NavLink>
              </li>
            ))}
          </ul>
          <p className="nav-footer">Analysis starts with a product. Select one to review or import feedback.</p>
        </nav>
        <main id="main-content" className="main-content" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
    </div>
  )
}
