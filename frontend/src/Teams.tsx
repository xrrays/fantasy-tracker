import { DataTable, fmt } from './components'
import type { Column } from './components'
import type { Team } from './types'

export default function Teams({ teams, select }: { teams: Team[]; select: (key: string) => void }) {
  const columns: Column<Team>[] = [
    { key: 'rank', label: 'Rank', value: t => t.rank },
    { key: 'team', label: 'Team', value: t => t.name, render: t => <button className="text-button" title={t.name} onClick={() => select(t.key)}>{t.name}</button> },
    { key: 'manager', label: 'Manager', value: t => t.manager },
    { key: 'wins', label: 'W', value: t => t.wins }, { key: 'losses', label: 'L', value: t => t.losses }, { key: 'ties', label: 'T', value: t => t.ties },
    { key: 'pct', label: 'Win %', value: t => t.win_pct, render: t => t.win_pct == null ? '-' : `${fmt(t.win_pct * 100, 1)}%` },
    { key: 'pf', label: 'PF', value: t => t.pf, render: t => fmt(t.pf) },
    { key: 'pa', label: 'PA', value: t => t.pa, render: t => fmt(t.pa) },
    { key: 'total', label: 'PF + PA', value: t => t.pf == null || t.pa == null ? null : t.pf + t.pa, render: t => fmt(t.pf == null || t.pa == null ? null : t.pf + t.pa) },
    { key: 'diff', label: 'Diff', value: t => t.pf == null || t.pa == null ? null : t.pf - t.pa, render: t => fmt(t.pf == null || t.pa == null ? null : t.pf - t.pa) },
    { key: 'avg', label: 'Avg PF', title: 'Average points for across complete regular-season weeks', value: t => t.average, render: t => fmt(t.average) },
    { key: 'schedule', label: 'Avg PA', title: 'Average opponent score across complete regular-season weeks', value: t => t.schedule_strength, render: t => fmt(t.schedule_strength) },
    { key: 'margin', label: 'Avg Margin', value: t => t.margin, render: t => fmt(t.margin) },
    { key: 'expected', label: 'xWins', title: 'Expected wins: sum of weekly all-play win shares; ties count as half a win. Complete regular-season weeks only.', value: t => t.expected_wins, render: t => fmt(t.expected_wins) },
    { key: 'moves', label: 'Moves', value: t => t.moves }, { key: 'trades', label: 'Trades', value: t => t.trades },
  ]
  return <section className="panel standings-panel"><DataTable rows={teams} columns={columns} rowKey={t => t.key} caption="League Standings"/></section>
}
