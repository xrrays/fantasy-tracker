import { useEffect, useState } from 'react'
import Home from './Home'
import Rosters, { RosterSelector } from './Rosters'
import Teams from './Teams'
import Managers, { ManagerSelector } from './Managers'
import Players, { PlayerCard, PlayerSearch } from './Players'
import History from './History'
import Editorial from './Editorial'
import type { Player, Snapshot } from './types'

const pages = ['Home', 'Standings', 'Rosters', 'Transactions', 'Players', 'History', 'Editorial']
function currentPage() {
  const slug = window.location.hash.slice(2).toLowerCase()
  const aliases: Record<string, string> = { columns: 'editorial', teams: 'standings', managers: 'transactions' }
  return pages.find(p => p.toLowerCase() === (aliases[slug] ?? slug)) ?? 'Home'
}
const initial: Snapshot = { data: null, running: false, message: 'Connecting to the local backend…', error: null, requests: 0, budget: 240 }
export default function App() {
  const [page, setPage] = useState(currentPage)
  const [snapshot, setSnapshot] = useState<Snapshot>(initial)
  const [selected, setSelected] = useState('')
  const [week, setWeek] = useState<number | null>(null)
  const [player, setPlayer] = useState<Player | null>(null)
  const [connectionError, setConnectionError] = useState('')
  const [retry, setRetry] = useState(0)
  const [cooldown, setCooldown] = useState(false)
  const [playerQuery, setPlayerQuery] = useState('')
  const [manager, setManager] = useState('all')
  const [rosterSelection,setRosterSelection]=useState('all')
  useEffect(() => { const handle = () => { setPage(currentPage()); setPlayer(null) }; window.addEventListener('hashchange', handle); return () => window.removeEventListener('hashchange', handle) }, [])
  useEffect(() => { document.title = `${page.toUpperCase()} · RAY` }, [page])
  useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>
    async function read(first = false) {
      try {
        const response = await fetch('/api/v1/dashboard', { signal: AbortSignal.timeout(12000) })
        if (!response.ok) throw new Error('Backend unavailable')
        let result: Snapshot = await response.json()
        if (first && (!result.data || result.refresh_due) && !result.running && !result.error) {
          const start = await fetch('/api/v1/refresh', { method: 'POST' })
          if (!start.ok) throw new Error('Refresh unavailable')
          result = await start.json()
        }
        if (!cancelled) { setSnapshot(result); setConnectionError(''); timer = setTimeout(() => read(), result.running ? 2000 : 15000) }
      } catch { if (!cancelled) { setConnectionError('The local data server is unavailable. Run npm run dev from frontend to start both servers.'); timer = setTimeout(() => read(), 15000) } }
    }
    void read(true)
    return () => { cancelled = true; clearTimeout(timer) }
  }, [retry])
  const data = snapshot.data
  const activeTeam = data?.teams.find(t => t.key === selected)?.key ?? data?.teams.find(t => t.key === data.favorite_team_key)?.key ?? data?.teams[0]?.key ?? ''
  const currentWeek = week != null && data?.matchups.some(m => m.week === week) ? week : data?.league.week ?? 1
  async function request(path: string) {
    try {
      const response = await fetch(path, { method: 'POST', signal: AbortSignal.timeout(12000) })
      if (!response.ok) throw new Error('Request failed')
      setSnapshot(await response.json()); setConnectionError(''); setRetry(v => v + 1)
      if (path.endsWith('/refresh')) { setCooldown(true); setTimeout(() => setCooldown(false), 60000) }
    } catch { setConnectionError('Could not start the data request. Check that the local backend is running.') }
  }
  const selectTeam = (key: string) => { setSelected(key); window.location.hash = '/home' }
  return <div className="app-shell"><a className="skip-link" href="#main-content" onClick={e => { e.preventDefault(); document.getElementById('main-content')?.focus() }}>Skip to Content</a>
    <header className="site-header"><a className="brand" href="#/home" aria-label="RAY Home"><span className="brand-name">RAY<span className="brand-dot">.</span></span><span className="brand-description">Fantasy Hockey League</span></a>
      <nav className="navigation" aria-label="Main Navigation">{pages.map(p => <a key={p} href={`#/${p.toLowerCase()}`} aria-current={p === page ? 'page' : undefined}>{p.toUpperCase()}</a>)}</nav>
      <div className="header-actions">{data && <small className="fetched-time">FETCHED {new Date(data.updated_at).toLocaleTimeString(undefined, { timeZone: 'America/Edmonton', hour: 'numeric', minute: '2-digit' }).toUpperCase()}</small>}<button className="refresh-button" disabled={snapshot.running || cooldown} onClick={() => void request('/api/v1/refresh')}>{snapshot.running ? 'FETCHING…' : cooldown ? 'REFRESHED' : '↻ REFRESH'}</button></div>
    </header>
    <main className={`page page-${page.toLowerCase()}`} id="main-content" tabIndex={-1}><h1 className="sr-only">{page.toUpperCase()}</h1><div className="page-toolbar">{page === 'Players' && <PlayerSearch query={playerQuery} change={setPlayerQuery}/>}<div className="home-selectors" hidden={page !== 'Home'}><label className="team-selector">SELECT A TEAM<select aria-label="Selected Team" value={activeTeam} onChange={e => setSelected(e.target.value)} disabled={!data}>{data ? data.teams.map(t => <option key={t.key} value={t.key}>{t.name}</option>) : <option>LOADING TEAMS…</option>}</select></label>{data && <select aria-label="Matchup Week" value={currentWeek} onChange={e => setWeek(Number(e.target.value))}>{[...new Set(data.matchups.map(m => m.week))].sort((a, b) => a - b).map(w => <option key={w} value={w}>Week {w}</option>)}</select>}</div>{data && page === 'Rosters' && <RosterSelector data={data} selected={rosterSelection} change={setRosterSelection}/>}
      {data && page === 'Transactions' && <ManagerSelector data={data} manager={manager} change={setManager}/>}<div className="context-controls">{data && <>{data.preview && <span className="tag">Synthetic Preview</span>}<span className="season-label">{data.league.season}–{String(Number(data.league.season) + 1).slice(-2)}</span></>}</div></div>
      {(snapshot.running || snapshot.error || connectionError) && <div className={`status-banner ${snapshot.error || connectionError ? 'error' : ''}`} role="status">{connectionError || snapshot.error || snapshot.message}{(snapshot.error || connectionError) && data && ' Showing last available data.'}</div>}
      {!data ? <div className="panel initial-state"><span className="loading-mark">R</span><h2>{connectionError || snapshot.error ? 'League Data Unavailable' : 'Loading Your League'}</h2><p>{connectionError || snapshot.error || snapshot.message}</p><small>One shared fetch, paced at two seconds per request. The first load can take a minute or two.</small><button onClick={() => void request('/api/v1/refresh')} disabled={snapshot.running}>Retry Connection</button></div> : <>
        <div hidden={page !== 'Home'}><Home data={data} selected={activeTeam} week={currentWeek}/></div>
        <div hidden={page !== 'Standings'}><Teams teams={data.teams} select={selectTeam}/></div>
        <div hidden={page !== 'Rosters'}><Rosters data={data} selected={rosterSelection} change={setRosterSelection} open={setPlayer} busy={snapshot.running} loadCredited={()=>void request('/api/v1/credited/refresh')}/></div>
        <div hidden={page !== 'Transactions'}><Managers data={data} manager={manager} open={setPlayer} busy={snapshot.running}/></div>
        <div hidden={page !== 'Players'}><Players data={data} query={playerQuery} open={setPlayer} busy={snapshot.running} loadRecent={days => void request(`/api/v1/recent/${days}`)}/></div>
        <div hidden={page !== 'History'}><History data={data} select={selectTeam}/></div>
        <div hidden={page !== 'Editorial'}><Editorial data={data}/></div>
      </>}
      {player && data && <PlayerCard key={player.key} player={player} labels={data.stat_labels} close={() => setPlayer(null)}/>}
    </main><footer className="yahoo-credit"><a href="https://hockey.fantasysports.yahoo.com/" target="_blank" rel="noreferrer">FANTASY DATA PROVIDED BY YAHOO FANTASY</a></footer>
  </div>
}
