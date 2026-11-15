import { useState } from 'react'
import { DataTable, Panel, fmt } from './components'
import Teams from './Teams'
import type { Dashboard } from './types'

const names = ['North Stars', 'Ice Merchants', 'Frozen Assets', 'Top Shelf', 'Crease Kings', 'Bench Mob', 'Hat Trick Club', 'Puck Luck', 'Slap Shots', 'Blue Line', 'Cold Front', 'Ice Wolves', 'Net Results', 'Goal Diggers', 'Overtime', 'Rink Rats']
export default function History({ data, select }: { data: Dashboard; select: (key: string) => void }) {
  const current = Number(data.league.season)
  const [year, setYear] = useState(current)
  const demo = Array.from({ length: 16 }, (_, i) => ({ rank: i + 1, name: names[(i + current - year) % 16], wins: 22 - i, losses: 4 + i, pf: 10000 - i * 173 + (current - year) * 21, pa: 8400 + i * 88 }))
  const label = (y: number) => `${y}–${String(y + 1).slice(-2)}`
  return <div className="stack"><div className="pills seasons" aria-label="Historical Season">{Array.from({ length: 6 }, (_, i) => current - i).map(y => <button key={y} onClick={() => setYear(y)} aria-pressed={year === y}>{label(y)}{y !== current && <small>Demo</small>}</button>)}</div>
    {year === current ? <><Teams teams={data.teams} select={select}/><Panel title="Playoff Bracket"><p className="empty">Not Available</p></Panel></> : <>
      <Panel title={`${label(year)} Standings`} aside={<span className="tag" title="Fictional teams, scores and results; this historical season is not connected">Demo Data</span>}><DataTable rows={demo} rowKey={t => t.name} caption="Demo Historical Standings" columns={[
        { key: 'rank', label: 'Rank', value: t => t.rank }, { key: 'name', label: 'Team', value: t => t.name },
        { key: 'wins', label: 'W', value: t => t.wins }, { key: 'losses', label: 'L', value: t => t.losses },
        { key: 'pf', label: 'PF', value: t => t.pf, render: t => fmt(t.pf) }, { key: 'pa', label: 'PA', value: t => t.pa, render: t => fmt(t.pa) },
      ]}/></Panel>
      <Panel title="Playoff Bracket · Demo"><div className="bracket">{[
        { title: 'Quarterfinals', pairs: [[0, 7], [3, 4], [1, 6], [2, 5]] },
        { title: 'Semifinals', pairs: [[0, 3], [1, 2]] }, { title: 'Final', pairs: [[0, 1]] },
      ].map(round => <div key={round.title}><h3>{round.title}</h3><div className="bracket-games">{round.pairs.map(([a, b]) => <div className="bracket-game" key={a}><strong>{demo[a].name}<span>{fmt(390 + year % 10 - a, 1)}</span></strong><span>{demo[b].name}<span>{fmt(365 - b, 1)}</span></span></div>)}</div></div>)}</div><p className="muted">Illustrative Champion: {demo[0].name}</p></Panel>
    </>}
  </div>
}
