import { useState } from 'react'
import type { Dashboard } from './types'

export default function Editorial({ data }: { data: Dashboard }) {
  const year = Number(data.league.season)
  const months = Array.from({ length: 8 }, (_, i) => new Date(year, 9 + i, 1))
  const now = new Date()
  const defaultMonth = months.find(d => d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth()) ?? months[0]
  const monthKey = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
  const [month, setMonth] = useState(monthKey(defaultMonth))
  const teams = new Map(data.teams.map(t => [t.key, t]))
  const published = data.jordog_editions ?? {}
  const previousMonth = new Date(`${month}-01T12:00:00`)
  previousMonth.setMonth(previousMonth.getMonth() - 1)
  const previous = published[monthKey(previousMonth)]
  const current = published[month] ?? []
  const ai = data.drake_editions?.[0]
  const priorAi = data.drake_editions?.[1]
  const editionDate = ai ? new Date(ai.published_at).toLocaleDateString(undefined, { timeZone: 'America/Edmonton', month: 'short', day: 'numeric', year: 'numeric' }).toUpperCase() : ''
  return <div className="editorial-grid">
    <div className="editorial-scene jordog-scene"><img className="editorial-character" src="/art/jordog-raised-hand.png" alt="" aria-hidden="true"/><img className="editorial-character character-hand" src="/art/jordog-raised-hand.png" alt="" aria-hidden="true"/>
    <section className="panel editorial-column jordog-column"><div className="editorial-content"><div className="editorial-heading"><div><h2>Jordog Power Rankings</h2><label>Month<select value={month} onChange={e => setMonth(e.target.value)}>{months.map(d => <option key={monthKey(d)} value={monthKey(d)}>{d.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })}</option>)}</select></label></div></div>
      {!current.length ? <div className="empty"><p>No Jordog edition for this month.</p></div> : <>
        <ol className="power-list" aria-label="Jordog Rankings">{current.map((key, i) => {
          const old = previous?.indexOf(key) ?? -1
          const delta = old >= 0 ? old - i : null
          return <li key={key}><span className="power-rank">{i + 1}</span><div><strong>{teams.get(key)?.manager ?? 'Manager Unavailable'}</strong><small>{teams.get(key)?.name}</small></div><span className="rank-movement" title="Movement from the previous month">{delta == null ? '-' : delta > 0 ? `↑ ${delta}` : delta < 0 ? `↓ ${-delta}` : '·'}</span></li>
        })}</ol>
      </>}</div>
    </section></div>
    <div className="editorial-scene drake-scene"><img className="editorial-character" src="/art/optimus-crossed-ovo-clean.png" alt="" aria-hidden="true"/>
    <section className="panel editorial-column drake-column"><div className="editorial-content"><div className="editorial-heading"><div><h2>DRAKE</h2><span className="tag">AI POWER RANKINGS</span>{ai && <time className="edition-date" dateTime={ai.published_at} title={`Based on completed regular-season results through Week ${ai.through_week}. League data fetched ${new Date(ai.source_updated_at).toLocaleString()}.`}>{editionDate}</time>}</div></div>
      {!ai ? <p className="empty">First Weekly Edition Pending</p> : <ol className="power-list ai-list" aria-label="DRAKE Rankings">{ai.entries.map(entry => {
        const previousRank = priorAi?.entries.find(old => old.team_key === entry.team_key)?.rank
        const delta = previousRank == null ? null : previousRank - entry.rank
        return <li key={entry.team_key}><span className="power-rank">{entry.rank}</span><div><strong>{entry.name ?? teams.get(entry.team_key)?.name ?? 'Team Unavailable'}</strong><p>{entry.blurb}</p></div><span className="rank-movement" title={priorAi ? 'Movement since the previous published week' : 'First published edition'}>{delta == null ? '-' : delta > 0 ? `↑ ${delta}` : delta < 0 ? `↓ ${-delta}` : '·'}</span></li>
      })}</ol>}
      </div>
    </section></div>
  </div>
}
