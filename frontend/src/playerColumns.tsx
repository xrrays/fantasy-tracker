import { fmt } from './components'
import type { Column } from './components'
import type { Dashboard, Player } from './types'

type Stats = Record<string, number | null>

export function productionColumns(data: Dashboard, points: (p: Player) => number | null, stats: (p: Player) => Stats): Column<Player>[] {
  const labels = data.stat_labels
  const hidden = new Set(['+/-','GTG','PIM','PPP','SHG','SHA','FW','FL','FOW','FOL','FO','GS','T','GAA','SA','TOI','MIN','MP'])
  const ids = [...new Set(data.players.flatMap(p => Object.keys(p.stats)))].sort((a,b) => Number(a)-Number(b))
  const seen = new Set<string>()
  const visible = ids.filter(id => {
    const label = labels[id] ?? `Stat ${id}`
    if (hidden.has(label) || seen.has(label)) return false
    seen.add(label)
    return true
  })
  const afterShots = ['HIT','BLK'].flatMap(label => visible.filter(id => labels[id] === label))
  const ordered = visible.filter(id => !afterShots.includes(id))
  const sog = ordered.findIndex(id => labels[id] === 'SOG')
  ordered.splice(sog < 0 ? ordered.length : sog+1, 0, ...afterShots)
  const value = (values: Stats, label: string) => Object.keys(labels).map(id => labels[id] === label ? values[id] : null).find(v => v != null) ?? null
  const games = (p: Player) => value(stats(p),'GP')
  const perGame = (p: Player) => points(p) != null && games(p) != null && games(p)! > 0 ? points(p)!/games(p)! : null
  const draft = new Map(data.draft.map(p => [p.player,p]))
  return [
    { key:'points', label:'Fan Pts', title:'League fantasy points over the selected period', value:points, render:p => <strong>{fmt(points(p),1)}</strong> },
    { key:'pergame', label:'FP / GP', title:'Fantasy points divided by actual games played', value:perGame, render:p => fmt(perGame(p),2) },
    { key:'draft', label:'Draft Pick', title:'Original round and overall pick; FA means undrafted', value:p => draft.get(p.key)?.pick ?? null, render:p => { const d=draft.get(p.key); return d ? `R${d.round??'?'} P${d.pick??'?'}` : 'FA' } },
    ...ordered.map(id => {
      const label = labels[id] ?? `Stat ${id}`
      const stat = (p:Player) => {
        if (label !== 'SH%') return label === 'GP' ? games(p) : stats(p)[id] ?? null
        const g=value(stats(p),'G'), shots=value(stats(p),'SOG')
        return g!=null && shots!=null && shots>0 ? g/shots*100 : null
      }
      return { key:`stat-${id}`, label:label==='TOI/G'?'TOI/GP':label, title:'Statistics for the selected period', value:stat, render:(p:Player) => {
        const v=stat(p)
        if (v==null) return '-'
        if (label==='TOI/G') { const seconds=Math.round(v*60); return `${Math.floor(seconds/60)}:${String(seconds%60).padStart(2,'0')}` }
        if (label==='SH%') return `${fmt(v,1)}%`
        return fmt(v,label==='SV%'?3:0)
      } }
    }),
  ]
}
