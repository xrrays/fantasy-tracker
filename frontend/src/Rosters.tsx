import { useState } from 'react'
import { DataTable, Panel, fmt } from './components'
import { productionColumns } from './playerColumns'
import type { Column } from './components'
import type { Dashboard, Player, RosterProfile } from './types'

export function RosterSelector({data,selected,change}:{data:Dashboard;selected:string;change:(key:string)=>void}) {
  return <label className="roster-selector">SELECT A TEAM<select aria-label="Selected Roster" value={selected} onChange={e=>change(e.target.value)}><option value="all">All Rosters</option>{data.teams.map(t=><option key={t.key} value={t.key}>{t.name}</option>)}</select></label>
}

export default function Rosters({data,selected,change,open,busy,loadCredited}:{data:Dashboard;selected:string;change:(key:string)=>void;open:(player:Player)=>void;busy:boolean;loadCredited:()=>void}) {
  const [period,setPeriod]=useState('season')
  const [position,setPosition]=useState('all')
  const [comparisonMode,setComparisonMode]=useState('totals')
  const [rosterMode,setRosterMode]=useState('current')
  const currentProfiles=data.roster_profiles?.[period] ?? []
  const creditInfo=data.credited?.coverage[period]
  const profiles=rosterMode==='credited'?data.credited?.profiles[period]??[]:currentProfiles
  const profile=currentProfiles.find(p=>p.key===selected)
  const leaders=rosterMode==='credited'&&!creditInfo?.complete?[]:profiles
  const reconcile=data.credited?.reconciliation
  const points=(p:Player)=>period==='season' ? p.points : data.recent[period]?.points[p.key] ?? null
  const roster=data.players.filter(p=>data.roster_owners?.[p.key]===selected && (position==='all'||p.group===position))
  const playerRanks=profile?.player_ranks ?? {}
  const stats=(p:Player)=>period==='season'?p.stats:data.recent[period]?.stats?.[p.key]??{}
  const profileTitle='Strength of the CURRENT roster using player production over the selected period, including bench and IR. Not historical starting-lineup credit. Total view ranks by total FP; average view ranks by FP per player; player ranks compare the loaded player pool. Equal values share ranks.'
  const allColumns:Column<RosterProfile>[]=[
    {key:'rank',label:comparisonMode==='totals'?'FP Rank':'Avg FP Rank',title:comparisonMode==='totals'?'Rank by total fantasy points for this view':'Rank by fantasy points per unique contributing player (credited) or current roster player (current)',value:r=>comparisonMode==='totals'?r.total_rank:r.rank},
    {key:'team',label:'Team / Manager',value:r=>r.name,render:r=><><button className="text-button" title={r.name} onClick={()=>change(r.key)}>{r.manager}</button><small title={r.name}>{r.name}</small></>},
    {key:'games',label:'Games Played',title:rosterMode==='credited'?"Games played in this team's starting lineup over the selected period":'Total NHL games played by current roster players',value:r=>r.stats.GP},
    {key:'points',label:'FP',title:'Total fantasy points over this period',value:r=>r.points,render:r=>fmt(r.points,1)},
    {key:'average',label:'Avg FP',title:'Fantasy points per unique contributing player (credited) or current roster player (current)',value:r=>r.average_points,render:r=><strong>{fmt(r.average_points,1)}</strong>},
    ...['F','D','G'].flatMap(group=>[
      {key:`${group}-points`,label:`${group} Pts`,title:`${rosterMode==='credited'?'Starting-lineup':'Current-roster'} ${group} fantasy points`,value:(r:RosterProfile)=>r.groups[group]?.points??null,render:(r:RosterProfile)=>fmt(r.groups[group]?.points,1)},
      {key:`${group}-rank`,label:`Avg ${group} Rank`,title:rosterMode==='credited'?`Mean ${group} contribution rank across team-player contributions; lower is better`:`Mean positional rank of ${group} players; lower is better`,value:(r:RosterProfile)=>r.groups[group]?.average_pos_rank??null,render:(r:RosterProfile)=>fmt(r.groups[group]?.average_pos_rank,1)},
      {key:`${group}-fp`,label:`Avg FP ${group}`,title:`Average fantasy points per ${group} player`,value:(r:RosterProfile)=>r.groups[group]?.average_points??null,render:(r:RosterProfile)=>fmt(r.groups[group]?.average_points,1)},
    ]),
    {key:'top100',label:'Top 100',title:rosterMode==='credited'?'Team-player contributions ranked in the top 100 over this period':'Current roster players in the top 100 of the loaded pool',value:r=>rosterMode==='credited'&&!creditInfo?.complete?null:r.top100},
    ...[['G','Goals'],['A','Assists'],['SOG','Shots'],['SV','Saves'],['W','Wins']].map(([id,label])=>({key:`total-${id}`,label,value:(r:RosterProfile)=>r.stats[id]??null})),
  ]
  const columns=allColumns.filter(column=>comparisonMode==='totals'?!['average','F-rank','F-fp','D-rank','D-fp','G-rank','G-fp'].includes(column.key):['rank','team','average','F-rank','F-fp','D-rank','D-fp','G-rank','G-fp'].includes(column.key))
  return <div className="stack roster-layout">
    <div className="roster-controls"><div className="pills" aria-label="Roster Points Period">{['season','7','14','30'].map(value=><button key={value} aria-pressed={period===value} onClick={()=>setPeriod(value)}>{value==='season'?'SEASON':`LAST ${value} DAYS`}</button>)}</div><span className="roster-period-context" title={rosterMode==='credited'&&selected==='all'?"Only production earned while in this team's active starting lineup; includes former players. Averages use unique players who appeared.":profileTitle}>{rosterMode==='credited'&&selected==='all'?`Started Players · ${creditInfo?`${creditInfo.start} to ${creditInfo.end}`:'Import Pending'}`:`Current Players · ${period==='season'?'Season Production':data.recent[period]?`${data.recent[period].start} to ${data.recent[period].end}`:'Period Not Loaded'}`}</span></div>
    {!data.rosters_loaded ? <div className="panel empty">Loading Current Rosters…</div> : selected==='all' ? <div className="roster-overview">
      <Panel title="Roster Comparison" aside={<div className="roster-view-controls"><div className="pills" aria-label="Roster Accounting View">{['current','credited'].map(mode=><button key={mode} aria-pressed={rosterMode===mode} onClick={()=>{setRosterMode(mode);if(mode==='credited'&&!data.credited?.coverage.season?.complete&&!busy)loadCredited()}}>{mode.toUpperCase()}</button>)}</div><div className="pills" aria-label="Roster Comparison View">{['totals','averages'].map(mode=><button key={mode} aria-pressed={comparisonMode===mode} onClick={()=>setComparisonMode(mode)}>{mode.toUpperCase()}</button>)}</div></div>}>
        {rosterMode==='credited'&&(!creditInfo?.complete?<div className="credit-status" role="status">{busy?'Importing starting lineups and daily production…':`Credited import incomplete: ${creditInfo?.covered??0} / ${creditInfo?.expected??0} dates loaded.`}{!busy&&<button onClick={loadCredited}>Resume Import</button>}</div>:reconcile&&reconcile.checked>0?<div className="credit-verification" title={reconcile.matched===reconcile.checked?`${reconcile.matched} completed team-weeks match Yahoo within 0.15 points.`:`${reconcile.matched}/${reconcile.checked} completed team-weeks match Yahoo. Figures below are reconstructed from starting lineups; unmatched official totals have not been substituted.`}>{reconcile.matched===reconcile.checked?'Verified Against Yahoo':reconcile.daily_checked&&reconcile.daily_checked===reconcile.daily_matched?`Daily Scores Verified · ${reconcile.checked-reconcile.matched} Weekly Differences`:`Lineup Totals · ${reconcile.matched}/${reconcile.checked} Team-Weeks Matched`}</div>:null)}
        <div className={`roster-comparison roster-comparison-${comparisonMode}`}><DataTable key={`${rosterMode}:${comparisonMode}`} rows={profiles} columns={columns} rowKey={r=>r.key} initialSort="rank" caption={rosterMode==='credited'?'Credited Production':'Roster Strength'}/></div>
      </Panel>
      <aside className="roster-leaders" aria-label="Roster Leaders">{['all','F','D','G'].map(group=>{
        const title=group==='all'?'Roster Leaders':group==='F'?'Forward Leaders':group==='D'?'Defense Leaders':'Goalie Leaders'
        return <Panel key={group} title={title} className="roster-leader-card">{['totals','averages'].map(mode=>{
          const field=mode==='totals'?'points':'average_points'
          const bucket=(r:RosterProfile)=>group==='all'?r:r.groups[group]
          const best=leaders.filter(r=>bucket(r)?.count && bucket(r)?.[field]!=null).sort((a,b)=>bucket(b)[field]!-bucket(a)[field]!)[0]
          return <div key={mode} className={`roster-leader-entry${comparisonMode===mode?' is-active':''}`}><span>{mode==='totals'?(rosterMode==='credited'?'Credited FP':'Total FP'):'Avg FP / Player'}</span><strong>{fmt(best?bucket(best)[field]:null,1)}</strong><button className="text-button" disabled={!best} title="View Current Roster" onClick={()=>best&&change(best.key)}>{best?.name??'-'}</button></div>
        })}</Panel>
      })}</aside>
    </div> : profile ? <>
      <Panel title="Roster Profile" aside={<button className="text-button" onClick={()=>change('all')}>All Rosters →</button>}>
        <div className="roster-profile"><div className="roster-profile-identity"><h3>{profile.name}</h3><p className="roster-manager-name">{profile.manager}</p><div className="roster-profile-score"><strong>{fmt(profile.average_points,1)}</strong><span>FP / Player</span></div><div className="roster-profile-facts"><span>Avg FP Rank <b>{profile.rank==null?'-':`#${profile.rank}`}</b></span><span>FP Rank <b>{profile.total_rank==null?'-':`#${profile.total_rank}`}</b></span></div></div>
          {['F','D','G'].map(group=>{const g=profile.groups[group];return <div className="roster-group-profile" key={group}><h3>{group==='F'?'Forwards':group==='D'?'Defense':'Goalies'}</h3><div className="roster-profile-score"><strong>{fmt(g?.average_points,1)}</strong><span>FP / Player</span></div><div className="roster-profile-facts"><span>Avg FP Rank <b>{g?.rank==null?'-':`#${g.rank}`}</b></span><span>Avg Player Rank <b>{fmt(g?.average_pos_rank,1)}</b></span><span>Players <b>{g?.count}</b></span></div></div>})}
        </div>
        <div className="roster-summary-stats">{[['Total FP',fmt(profile.points,1)],['Games Played',fmt(profile.stats.GP,0)],['FP Per Game',profile.stats.GP && profile.points!=null?fmt(profile.points/profile.stats.GP,2):'-'],['Top 100',String(profile.top100)],['Goals',fmt(profile.stats.G,0)],['Assists',fmt(profile.stats.A,0)],['Shots',fmt(profile.stats.SOG,0)],['Saves',fmt(profile.stats.SV,0)],['Wins',fmt(profile.stats.W,0)]].map(([label,value])=><div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>
      </Panel>
      <Panel className="roster-players-panel" title="Current Players" aside={<div className="pills roster-position-filter" aria-label="Roster Position">{['all','F','D','G'].map(group=><button key={group} aria-pressed={position===group} onClick={()=>setPosition(group)}>{group==='all'?'ALL':group}</button>)}</div>}>
        <DataTable key={`${selected}:${period}`} rows={roster} rowKey={p=>p.key} initialSort="points" initialDesc allRows caption="Current Roster Players" columns={[
          {key:'rank',label:'Rank',value:p=>playerRanks[p.key]?.rank??null},
          {key:'posrank',label:'Pos Rank',value:p=>playerRanks[p.key]?.pos_rank??null,render:p=>playerRanks[p.key]?.pos_rank==null?'-':`${p.group}${playerRanks[p.key].pos_rank}`},
          {key:'name',label:'Player',value:p=>p.name,render:p=><button className="text-button" onClick={()=>open(p)}>{p.name}</button>},
          {key:'nhl',label:'NHL',value:p=>p.nhl_team}, {key:'pos',label:'Pos',value:p=>p.positions.join('/')},
          ...productionColumns(data,points,stats),
        ]}/>
      </Panel>
    </> : <div className="panel empty">Roster Profile Unavailable</div>}
  </div>
}
