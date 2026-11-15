import { useEffect, useRef, useState } from 'react'
import { DataTable, fmt } from './components'
import { productionColumns } from './playerColumns'
import type { Column } from './components'
import type { Dashboard, Player } from './types'

function Headshot({ player, lazy = false }: { player: Player; lazy?: boolean }) {
  const [fallback, setFallback] = useState(false)
  return <img src={fallback ? player.image_fallback || player.image : player.image} alt="" loading={lazy ? 'lazy' : 'eager'} onError={() => setFallback(true)}/>
}

export function PlayerCard({ player, labels, close }: { player: Player; labels: Record<string, string>; close: () => void }) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => { const dialog = ref.current; if (dialog && !dialog.open) dialog.showModal() }, [])
  return <dialog ref={ref} onClose={close} onClick={e => { if (e.target === e.currentTarget) close() }} aria-labelledby="player-name">
    <button className="close-button" onClick={close} aria-label="Close Player Card">×</button>
    <div className="player-identity">{player.image && <Headshot key={player.image} player={player}/>}<div><small>{player.nhl_team} · {player.positions.join(' / ')}</small><h2 id="player-name">{player.name}</h2>{player.status && <p>{player.status}</p>}</div></div>
    <div className="player-summary"><span>Season Fantasy Points</span><strong>{fmt(player.points)}</strong></div>
    <dl className="stat-grid">{Object.entries(player.stats).map(([id, value]) => <div key={id}><dt>{labels[id] ?? `Stat ${id}`}</dt><dd>{fmt(value, 1)}</dd></div>)}</dl>
  </dialog>
}

export function PlayerSearch({ query, change }: { query: string; change: (value: string) => void }) {
  return <div className="player-search"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10" cy="10" r="6.5"/><path d="m15 15 6 6"/></svg><input aria-label="Search by Player" type="search" value={query} onChange={e => change(e.target.value)} placeholder="SEARCH BY PLAYER"/></div>
}

const statusCode = (p: Player) => {
  if (p.status_code) return p.status_code.toUpperCase()
  const value = p.status.toLowerCase()
  if (!value) return ''
  if (value.includes('reserve+') || value.includes('reserve plus')) return 'IR+'
  if (value.includes('reserve')) return 'IR'
  if (value.includes('not active') || value === 'na') return 'NA'
  if (value.includes('day-to-day')) return 'DTD'
  if (value === 'out') return 'O'
  if (value.includes('suspend')) return 'SUSP'
  return p.status.toUpperCase().slice(0, 4)
}

export default function Players({ data, query, open, loadRecent, busy }: { data: Dashboard; query: string; open: (p: Player) => void; loadRecent: (days: number) => void; busy: boolean }) {
  const [period, setPeriod] = useState('season')
  const [position, setPosition] = useState('all')
  const [nhl, setNhl] = useState('all')
  const [roster, setRoster] = useState('all')
  const [status, setStatus] = useState('all')
  const requested = useRef(new Set<string>())
  const recent = period === 'season' ? undefined : data.recent[period]
  useEffect(() => {
    if (period === 'season' || (recent?.complete && recent?.stats && data.players.every(p => p.key in recent.stats!)) || busy || !data.players_loaded) return
    const key = `${data.updated_at}:${period}:${new Date().toDateString()}`
    if (requested.current.has(key)) return
    requested.current.add(key)
    loadRecent(Number(period))
  }, [period, recent, busy, data.players_loaded, data.updated_at, loadRecent])
  const teams = new Map(data.teams.map(t => [t.key, t]))
  const owner = (p: Player) => data.roster_owners?.[p.key]
  const ownerName = (p: Player) => teams.get(owner(p) ?? '')?.name ?? (data.rosters_loaded ? 'Free Agent' : 'Loading…')
  const points = (p: Player) => period === 'season' ? p.points : recent?.points[p.key] ?? null
  const stats = (p: Player) => period === 'season' ? p.stats : recent?.stats?.[p.key] ?? {}
  const rank = (p: Player, positionOnly = false) => points(p) == null ? null : 1 + data.players.filter(x => (!positionOnly || x.group === p.group) && points(x) != null && points(x)! > points(p)!).length
  const pool = data.players.filter(p => (position === 'all' || (position === 'F' ? p.positions.some(pos => ['C', 'LW', 'RW', 'F'].includes(pos)) : p.group === position || p.positions.includes(position))) &&
    (nhl === 'all' || p.nhl_team === nhl) && (roster === 'all' || owner(p) === roster) &&
    (status === 'all' || (data.rosters_loaded && (status === 'rostered' ? Boolean(owner(p)) : !owner(p)))) &&
    p.name.toLowerCase().includes(query.toLowerCase().trim()))
  const columns: Column<Player>[] = [
    { key: 'rank', label: 'Rank', value: p => rank(p) },
    { key: 'posrank', label: 'Pos Rank', title: 'Fantasy-points rank within F, D or G over the selected period, across the loaded pool', value: p => rank(p, true), render: p => rank(p, true) == null ? '-' : `${p.group}${rank(p, true)}` },
    { key: 'name', label: 'Player', value: p => p.name, render: p => <button className="text-button player-table-name" title={p.name} aria-label={p.name} onClick={() => open(p)}><span className="player-name-text">{p.name}</span>{p.status && <span className="player-status" title={p.status}>{statusCode(p)}</span>}</button> },
    { key: 'nhl', label: 'NHL', value: p => p.nhl_team },
    { key: 'position', label: 'Pos', value: p => p.positions.join('/') },
    { key: 'owner', label: 'Fantasy Roster', value: ownerName, render: p => <><span className="player-roster-name" title={ownerName(p)}>{ownerName(p)}</span><small>{teams.get(owner(p) ?? '')?.manager}</small></> },
    ...productionColumns(data,points,stats),
  ]
  return <div className="player-explorer">
    <section className="player-filters" aria-label="Player Filters">
      <div className="filter-period"><div className="pills" aria-label="Points Period">{['season', '7', '14', '30'].map(n => <button key={n} aria-pressed={period === n} onClick={() => setPeriod(n)}>{n === 'season' ? 'SEASON' : `LAST ${n} DAYS`}</button>)}</div>
        <small className="period-coverage" title={period === 'season' ? 'Loaded pool: season leaders, drafted players and players in completed transactions; not every eligible NHL player.' : recent ? `${recent.start} through ${recent.end}. All columns use this period. Coverage includes the full loaded player list; unavailable values are not zero.` : 'The selected period loads automatically within the shared request budget.'}>{period === 'season' ? `${pool.length} Players` : recent ? `${pool.filter(p => points(p) != null).length}/${pool.length} Players Covered${recent.paused ? ' · Paused at Local Request Limit' : recent.complete === false ? ' · Partial' : ''}` : busy ? 'Loading…' : 'Not Loaded'}</small>
      </div>
      <div className="filter-selectors"><label>Fantasy Roster<select value={roster} onChange={e => { setRoster(e.target.value); if (e.target.value !== 'all') setStatus('rostered') }}><option value="all">All Rosters</option>{data.teams.map(t => <option key={t.key} value={t.key}>{t.manager} · {t.name}</option>)}</select></label>
        <label>NHL Team<select value={nhl} onChange={e => setNhl(e.target.value)}><option value="all">All NHL Teams</option>{[...new Set(data.players.map(p => p.nhl_team))].filter(Boolean).sort().map(team => <option key={team}>{team}</option>)}</select></label>
        <label>Position<select value={position} onChange={e => setPosition(e.target.value)}>{[['all', 'All Positions'], ['F', 'Forwards'], ['D', 'Defense'], ['G', 'Goalies'], ['C', 'Center'], ['LW', 'Left Wing'], ['RW', 'Right Wing']].map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
        <label>Status<select value={status} onChange={e => { setStatus(e.target.value); if (e.target.value === 'unrostered') setRoster('all') }}><option value="all">All Players</option><option value="rostered">Rostered</option><option value="unrostered">Unrostered</option></select></label>
        <button className="reset-filters" onClick={() => { setPosition('all'); setNhl('all'); setRoster('all'); setStatus('all'); setPeriod('season') }}>Reset Filters</button>
      </div>
    {period !== 'season' && recent?.complete === false && <div className="recent-import-state" role="status"><span>{recent.paused ? 'Import paused at the local daily request limit. Saved progress is retained; unavailable stats show -.' : 'Some player dates are still unavailable. Saved results are retained.'}</span><button disabled={busy} onClick={() => loadRecent(Number(period))}>{busy ? 'Loading…' : 'Resume Import'}</button></div>}
    </section>
    <section className="panel player-table-panel"><DataTable key={period} rows={pool} columns={columns} rowKey={p => p.key} initialSort="points" initialDesc scrollRows={12} caption="Player Statistics"/>
      {!data.players_loaded && <p role="status">Loading Players…</p>}
    </section>
  </div>
}
