import { useEffect, useState } from 'react'

const pages = [
  { id: 'home', label: 'Home' },
  { id: 'teams', label: 'Teams' },
  { id: 'players', label: 'Players' },
  { id: 'history', label: 'History' },
  { id: 'columns', label: 'Columns' },
] as const

function currentPage() {
  return pages.find((page) => window.location.hash === `#/${page.id}`) ?? pages[0]
}

export default function App() {
  const [activePage, setActivePage] = useState(currentPage)

  useEffect(() => {
    const handleNavigation = () => setActivePage(currentPage())
    window.addEventListener('hashchange', handleNavigation)
    return () => window.removeEventListener('hashchange', handleNavigation)
  }, [])

  useEffect(() => {
    document.title = `${activePage.label} · THO-RAY`
  }, [activePage])

  return (
    <div className="app-shell">
      <a
        className="skip-link"
        href="#main-content"
        onClick={(event) => {
          event.preventDefault()
          document.getElementById('main-content')?.focus()
        }}
      >
        Skip to Content
      </a>

      <header className="site-header">
        <a className="brand" href="#/home" aria-label="THO-RAY Home">
          <span className="brand-name">THO-RAY</span>
          <span className="brand-description">Fantasy Hockey League</span>
        </a>

        <nav className="navigation" aria-label="Main Navigation">
          {pages.map((page) => (
            <a
              key={page.id}
              className="navigation-link"
              href={`#/${page.id}`}
              aria-current={activePage.id === page.id ? 'page' : undefined}
            >
              {page.label}
            </a>
          ))}
        </nav>
      </header>

      <main id="main-content" className="page" tabIndex={-1}>
        <h1>{activePage.label}</h1>
        <section className="placeholder" aria-label={`${activePage.label} Placeholder`}>
          <p>{activePage.label} content will go here.</p>
        </section>
      </main>
    </div>
  )
}
