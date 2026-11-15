import { useEffect, useRef, useState } from 'react'
import { Panel, fmt, signed } from './components'
import type { Dashboard, Matchup } from './types'

function DailyChart({ data, matchup }: { data: Dashboard; matchup: Matchup }) {
  const chart = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(720)
  useEffect(() => {
    const element = chart.current
    if (!element) return
    const observer = new ResizeObserver(([entry]) => { if (entry.contentRect.width) setWidth(Math.round(entry.contentRect.width)) })
    observer.observe(element)
    return () => observer.disconnect()
  }, [matchup.week, data.daily_by_week, data.daily])
  const [a, b] = matchup.teams
  let ca = 0, cb = 0, complete = true
  const daily = data.daily_by_week?.[String(matchup.week)] ?? (matchup.week === data.league.week ? data.daily : [])
  const values = daily.map(day => {
    const av = day.scores[a.key], bv = day.scores[b.key]
    if (av == null || bv == null) complete = false
    ca += av ?? 0; cb += bv ?? 0
    return { date: day.date, a: ca, b: cb }
  })
  const finalized = matchup.status === 'postevent'
  const reconciled = !finalized || (values.at(-1)?.date === matchup.end && a.points != null && b.points != null && Math.abs(ca - a.points) < .15 && Math.abs(cb - b.points) < .15)
  if (!values.length || !complete) return <div className="chart-empty"><span className="chart-icon">â†—</span><p>Daily Matchup Trend</p><small>{values.length ? 'Some daily points are unavailable. Missing scores are not treated as zero.' : 'Daily points are loading. The scoreboard above is available now.'}</small></div>
  const min = Math.min(0, ...values.flatMap(v => [v.a, v.b]))
  const max = Math.max(1, ...values.flatMap(v => [v.a, v.b]))
  const start = new Date(`${matchup.start}T12:00:00Z`)
  const days = Math.min(14, Math.max(values.length, Math.round((Date.parse(matchup.end) - Date.parse(matchup.start)) / 86400000) + 1))
  const dates = Array.from({ length: days }, (_, i) => new Date(start.getTime() + i * 86400000).toISOString().slice(0, 10))
  const x = (i: number) => 38 + i / Math.max(1, dates.length - 1) * (width - 54)
  const y = (n: number) => 110 - (n - min) / (max - min) * 95
  const path = (key: 'a' | 'b') => values.map((v, i) => `${x(i)},${y(v[key])}`).join(' ')
  return <div className="daily-chart" ref={chart}><div className="chart-label"><h3>Daily Matchup Trend</h3><small className={!reconciled ? 'trend-discrepancy' : undefined} title={!reconciled ? "Yahoo's daily totals differ from its finalized weekly result. The graph shows the returned daily values; this matchup is excluded from comeback records." : "Completed-day totals; today's live points remain in the scoreboard"}>Through {values.at(-1)?.date.slice(5)} · Fantasy Points{!reconciled && ' · Final Differs'}</small></div>
    <svg viewBox={`0 0 ${width} 140`} role="img" aria-label={`Cumulative points: ${a.name} and ${b.name}`}>
      {[min, (max + min) / 2, max].map(n => <g key={n}><line x1="38" x2={width - 8} y1={y(n)} y2={y(n)} stroke="#3b3e42"/><text x="0" y={y(n) + 4}>{fmt(n, 0)}</text></g>)}
      <polyline points={path('b')} stroke="#b3b8bc"/><polyline points={path('a')} stroke="#f47c26"/>
      {dates.map((day, i) => <text key={day} x={x(i)} y="133" textAnchor="middle">{new Date(`${day}T12:00:00`).toLocaleDateString(undefined, { weekday: 'short' })}</text>)}
    </svg><div className="chart-legend"><span><i className="dot orange"/>{a.name}</span><span><i className="dot"/>{b.name}</span></div>
    <div className="deficits"><span>Lead / Deficit</span>{dates.map((day, i) => <div key={day}><small>{day.slice(5)}</small><strong>{values[i] ? signed(values[i].a - values[i].b) : '-'}</strong></div>)}</div>
  </div>
}

export default function Home({ data, selected, week }: { data: Dashboard; selected: string; week: number }) {
  const team = data.teams.find(t => t.key === selected) ?? data.teams[0]
  const matches = data.matchups.filter(m => m.week === week)
  const found = matches.find(m => m.teams.some(t => t.key === team?.key))
  const matchup = found ? { ...found, teams: [...found.teams].sort(a => a.key === team.key ? -1 : 1) } : undefined
  const pfRank = team?.pf == null ? null : 1 + data.teams.filter(t => t.pf != null && t.pf > team.pf!).length
  const paRank = team?.pa == null ? null : 1 + data.teams.filter(t => t.pa != null && t.pa < team.pa!).length
  const apRank = team?.expected_wins == null ? null : 1 + data.teams.filter(t => t.expected_wins != null && t.expected_wins > team.expected_wins!).length
  if (!team) return <p>No team data available.</p>
  const [a, b] = matchup?.teams ?? []
  return <div className="home-grid">
    <Panel title="Current Matchup" className="matchup-panel" aside={<small>{matchup?.status === 'postevent' ? 'Final' : matchup?.status === 'midevent' ? 'In Progress' : 'Upcoming'}</small>}>
      {matchup ? <><div className="scoreboard"><div><h3>{a.name}</h3><strong>{fmt(a.points)}</strong></div><span>vs</span><div><h3>{b.name}</h3><strong>{fmt(b.points)}</strong></div></div>
        <p className="matchup-margin">{a.points == null || b.points == null ? 'Score unavailable' : a.points === b.points ? 'Tied' : `${a.points > b.points ? 'Leading' : 'Trailing'} by ${fmt(Math.abs(a.points - b.points))} Pts`}</p>
        <DailyChart data={data} matchup={matchup}/></> : <p className="empty">No matchup for this team in the selected week.</p>}
    </Panel>
    <Panel title="Season Profile" className="profile-panel"><p className="muted">{team.name}</p><strong className="big-record"><span>{fmt(team.wins, 0)}</span><span className="record-separator">–</span><span>{fmt(team.losses, 0)}</span><span className="record-separator">–</span><span>{fmt(team.ties, 0)}</span></strong>
      <dl>{[
        { label: 'Standing', rank: team.rank, value: team.win_pct == null ? '-' : fmt(team.win_pct * 100, 1), title: 'Win percentage and official standing', unit: 'W%' },
        { label: 'Points For', rank: pfRank, value: fmt(team.pf, 1), title: 'Season points for and scoring rank' },
        { label: 'Points Against', rank: paRank, value: fmt(team.pa, 1), title: 'Season points against; lowest total ranks first' },
        { label: 'xWins', rank: apRank, value: fmt(team.expected_wins), title: 'Expected wins across complete regular-season weeks and rank' },
      ].map(metric => <div key={metric.label}><dt title={metric.title}>{metric.label}</dt><dd><span className="profile-number" title={metric.title}>{metric.value}{metric.unit && <small>{metric.unit}</small>}</span><span className="profile-rank">{metric.rank == null ? '-' : `#${metric.rank}`}</span></dd></div>)}</dl>
    </Panel>
    <Panel title="Around the League" className="league-panel" aside={<small>Week {week}</small>}>
      <div className="matchup-list">{matches.filter(m => !m.teams.some(t => t.key === team.key)).map(m => <div className="mini-matchup" key={m.teams[0].key}>{m.teams.map(t => <div key={t.key} className={t.points != null && t.points === Math.max(...m.teams.map(x => x.points ?? -Infinity)) ? 'leader' : ''}><span>{t.name}</span><strong>{fmt(t.points)}</strong></div>)}</div>)}</div>
    </Panel>
    <Panel title="Season Record Book" className="records-panel" aside={<small>{data.league.season}–{String(Number(data.league.season) + 1).slice(-2)}</small>}><div className="record-grid">
      <div title={`Largest end-of-day deficit overcome to win. ${data.records.comeback_covered ?? 0} finalized matchups reconciled with daily totals; mismatching matchups are excluded.`}><h3>Biggest Verified Comeback</h3><strong>{fmt(data.records.comeback?.deficit)}</strong><p>{data.records.comeback ? `${data.records.comeback.team} · Week ${data.records.comeback.week}` : data.records.comeback_covered ? 'No qualifying comeback' : 'Loading daily history…'}</p></div>
      <div><h3>Highest Weekly Score</h3><strong>{fmt(data.records.highest?.points)}</strong><p>{data.records.highest ? `${data.records.highest.team} · Week ${data.records.highest.week}` : 'No completed weeks yet'}</p></div>
      <div><h3>Closest Finish</h3><strong>{fmt(data.records.closest?.margin)}</strong><p>{data.records.closest ? `${data.records.closest.teams.join(' vs ')} · Week ${data.records.closest.week}` : 'No completed non-tied matchup yet'}</p></div>
    </div></Panel>
  </div>
}
