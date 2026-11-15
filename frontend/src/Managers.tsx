import { useEffect, useState } from 'react'
import { DataTable, Panel, fmt } from './components'
import type { Dashboard, Move, Player } from './types'

export function ManagerSelector({ data, manager, change }: { data: Dashboard; manager: string; change: (key: string) => void }) {
  return <label className="manager-selector">SELECT A MANAGER<select aria-label="Select a Manager" value={manager} onChange={e => change(e.target.value)}><option value="all">All Managers</option>{data.teams.map(t => <option key={t.key} value={t.key}>{t.manager} · {t.name}</option>)}</select></label>
}

export default function Managers({ data, manager, open, busy }: { data: Dashboard; manager: string; open: (p: Player) => void; busy: boolean }) {
  const [movePage, setMovePage] = useState(0)
  const [tradePage, setTradePage] = useState(0)
  const [activityTab,setActivityTab]=useState('moves')
  useEffect(() => { setMovePage(0); setTradePage(0) }, [manager])
  const players = new Map(data.players.map(p => [p.key, p]))
  const teams = new Map(data.teams.map(t => [t.key, t]))
  const playerButton = (key: string, fallback = 'Unknown Player') => {
    const p = players.get(key)
    return p ? <button className="text-button" onClick={() => open(p)}>{p.name}</button> : fallback
  }
  const adds = (data.pickups ?? []).filter(p => manager === 'all' || p.team === manager)
  const drafted = data.draft.filter(p => players.get(p.player)?.points != null)
  const productionRank = (key: string) => 1 + drafted.filter(p => players.get(p.player)!.points! > players.get(key)!.points!).length
  const picks = drafted.filter(p => manager === 'all' || p.team === manager).map(p => ({ ...p, points: players.get(p.player)!.points!, production_rank: productionRank(p.player), value: (p.pick ?? 0) - productionRank(p.player) })).sort((a, b) => b.value - a.value)
  const moves = data.transactions.filter(tx => manager === 'all' || tx.players.some(p => p.source === manager || p.destination === manager)).sort((a, b) => Number(b.timestamp) - Number(a.timestamp))
  const waiverMoves=moves.filter(tx=>tx.players.some(p=>p.action==='add'&&p.source_type==='waivers'))
  const managerTeam = (key: string) => <>{teams.get(key)?.manager ?? '-'}<small>{teams.get(key)?.name}</small></>
  const activity = (items: Move[], label: string, page: number, change: (page: number) => void) => {
    const count = Math.max(1, Math.ceil(items.length / 15))
    const current = Math.min(page, count - 1)
    return <section><div className="activity-heading">{label==='Adds & Drops'||label==='Waiver Claims'?<div className="pills activity-tabs" aria-label="Transaction Activity"><button aria-pressed={activityTab==='moves'} onClick={()=>{setActivityTab('moves');setMovePage(0)}}>Adds & Drops</button><button aria-pressed={activityTab==='waivers'} onClick={()=>{setActivityTab('waivers');setMovePage(0)}}>Waiver Claims</button></div>:<h3>{label}</h3>}<div className="activity-pagination"><button disabled={current === 0} aria-label={`Previous ${label}`} onClick={() => change(current - 1)}>←</button><span>{items.length ? `${current * 15 + 1}–${Math.min((current + 1) * 15, items.length)}` : '0'} / {items.length}</span><button disabled={current === count - 1} aria-label={`Next ${label}`} onClick={() => change(current + 1)}>→</button></div></div><div key={`${manager}:${current}:${activityTab}`} className="activity-scroll" tabIndex={0} role="region" aria-label={label}><div className="activity-list">{items.slice(current * 15, (current + 1) * 15).map(tx => <article key={tx.id}>
    <time dateTime={new Date(Number(tx.timestamp) * 1000).toISOString()}>{new Date(Number(tx.timestamp) * 1000).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</time>
    {tx.type === 'trade' ? <div className="trade-receivers">{[...new Set(tx.players.map(p => p.destination).filter((key): key is string => Boolean(key)))].map(teamKey => {
      const value=data.trade_production?.[tx.id]?.[teamKey]
      return <section className="trade-side" key={teamKey}><div className="trade-team-detail"><h4><span className="trade-direction">RECEIVES</span>{teams.get(teamKey)?.manager ?? 'Manager'}<small>{teams.get(teamKey)?.name}</small></h4><ul>{tx.players.filter(p => p.destination === teamKey).map((p,i)=><li className="trade-player-row" key={`${p.player}:${i}`}><span>{playerButton(p.player,p.name)}</span><span className="trade-player-value" title={value?.players?.[p.player]?`${value.start} through ${value.end}. ${value.players[p.player].covered}/${value.players[p.player].expected} days loaded. Same production basis as the receiving-side total.`:'Player production unavailable.'}>{value?.players?.[p.player]?.points==null?'-':`${value.players[p.player].points!>=0?'+':''}${fmt(value.players[p.player].points,2)}`}{value?.players?.[p.player]?.points!=null&&!value.players[p.player].complete&&<sup>†</sup>}</span></li>)}</ul></div><div className="trade-value" title={value?`${value.start} through ${value.end}. Player fantasy production since the processed trade date, including production after subsequent moves; not starting-lineup credit. ${value.covered}/${value.expected} player-days loaded.`:'Post-trade production is loading.'}><span>FAN PTS GAINED</span><strong>{value?.points==null?'-':`${value.points>=0?'+':''}${fmt(value.points,2)}`}{value?.points!=null&&!value.complete&&<sup>†</sup>}</strong></div></section>
    })}</div> : <ul>{tx.players.filter(p=>label!=='Waiver Claims'||(p.action==='add'&&p.source_type==='waivers')).map((p, i) => <li key={`${p.player}:${i}`}><span>{playerButton(p.player, p.name)} <span className="move-action">{p.action}</span></span><small>{p.source ? teams.get(p.source)?.name : p.source_type} → {p.destination ? teams.get(p.destination)?.name : 'waivers / freeagents'}</small></li>)}</ul>}
  </article>)}</div>{!items.length && <p className="empty">{data.managers_loaded ? `No ${label.toLowerCase()}` : 'Loading…'}</p>}</div></section>
  }
  return <div className="stack managers-layout">
    <Panel title="Moves & Trades"><div className="activity-columns">{activity(activityTab==='waivers'?waiverMoves:moves.filter(tx => tx.type !== 'trade'), activityTab==='waivers'?'Waiver Claims':'Adds & Drops', movePage, setMovePage)}{activity(moves.filter(tx => tx.type === 'trade'), 'Trades', tradePage, setTradePage)}</div></Panel>
    <div className="two-columns manager-leaderboards">
    <Panel title="Best Pickups" aside={!data.transactions_complete || (busy && !data.pickups_loaded) ? <small role="status" title={`${data.transactions.length} completed transactions loaded. Points are player production during the acquisition spell.`}>{!data.transactions_complete ? 'Partial History' : 'Calculating…'}</small> : undefined}>
      <DataTable rows={adds} rowKey={p => p.id} initialSort="points" initialDesc scrollRows={9} caption="Points Gained Since Pickup" columns={[
        { key: 'player', label: 'Player', value: p => players.get(p.player)?.name ?? p.name, render: p => <>{playerButton(p.player, p.name)}{p.active && (!data.rosters_loaded || data.roster_owners?.[p.player] === p.team) && <sup className="active-pickup" title="Still held by this fantasy team">*</sup>}</> },
        { key: 'manager', label: 'Team / Manager', value: p => teams.get(p.team)?.manager ?? '-', render: p => managerTeam(p.team) },
        { key: 'date', label: 'Added', value: p => p.start },
        { key: 'source', label: 'Source', value: p => p.source === 'waivers' ? 'Waiver' : 'FA' },
        { key: 'points', label: 'Points', title: 'Fantasy production during the pickup spell, ending before the next drop or trade; not started-lineup credit', value: p => p.points, render: p => <span className={p.points_complete === false ? 'partial-points' : undefined} title={`${p.start} through ${p.end} · ${p.covered_days}/${p.days} days loaded${p.points_complete === false ? '. Provisional sum of available days; missing days are not zero.' : ''}`}>{fmt(p.points)}{p.points != null && p.points_complete === false && <sup>†</sup>}</span> },
      ]}/>
    </Panel>
    <Panel title="Best Draft Picks">
      <DataTable rows={picks} rowKey={p => String(p.pick)} initialSort="value" initialDesc scrollRows={9} caption="Draft Value" columns={[
        { key: 'pick', label: 'Pick', value: p => p.pick }, { key: 'round', label: 'Round', value: p => p.round },
        { key: 'player', label: 'Player', value: p => players.get(p.player)?.name ?? '', render: p => playerButton(p.player) },
        { key: 'team', label: 'Draft Team', value: p => teams.get(p.team)?.manager ?? '-', render: p => managerTeam(p.team) },
        { key: 'current', label: 'Current Team', value: p => teams.get(data.roster_owners?.[p.player] ?? '')?.manager ?? (data.rosters_loaded ? 'Free Agent' : null), render: p => data.roster_owners?.[p.player] ? managerTeam(data.roster_owners[p.player]) : data.rosters_loaded ? 'Free Agent' : '-' },
        { key: 'points', label: 'Points', value: p => p.points, render: p => fmt(p.points) },
        { key: 'production', label: 'Rank', title: 'Season fantasy-points rank within the drafted-player pool', value: p => p.production_rank },
        { key: 'value', label: 'Value', title: 'Overall pick minus production rank. Positive values indicate outperforming the draft slot.', value: p => p.value },
      ]}/>
    </Panel>
    </div>
  </div>
}
